import time
import os
import joblib
import streamlit as st
from dotenv import load_dotenv
from firebase_store import FirebaseSessionStore
from system_prompts import get_unified_reel_prompt  # Cambiar de get_unified_puv_prompt a get_unified_reel_prompt
from reel_formulas import reel_formulas
from session_state import (
    SessionState,
    DEFAULT_GEMINI_MODEL,
    DATA_DIR,
)

# Inicializar el estado de la sesión
state = SessionState()
STREAM_SETTINGS = {'batch_size': 1, 'delay_seconds': 0.01}

# Función para detectar saludos y generar respuestas personalizadas
def is_greeting(text):
    """Detecta si el texto es un saludo simple"""
    text = text.lower().strip()
    greetings = ['hola', 'hey', 'saludos', 'buenos días', 'buenas tardes', 'buenas noches', 'hi', 'hello']
    
    # Solo considerar como saludo si es el primer mensaje del usuario
    # y es un saludo simple
    is_simple_greeting = any(greeting in text for greeting in greetings) and len(text.split()) < 4
    return is_simple_greeting and len(state.messages) == 0

# Función para procesar mensajes (unifica la lógica de procesamiento)
def process_message(prompt, is_example=False):
    """Procesa un mensaje del usuario, ya sea directo o de un ejemplo"""
    handle_chat_title(prompt)
    
    with st.chat_message('user', avatar=USER_AVATAR_ICON):
        st.markdown(prompt)
    
    state.add_message('user', prompt, USER_AVATAR_ICON)
    
    # Obtener el prompt mejorado primero
    enhanced_prompt = get_enhanced_prompt(prompt, is_example)
    
    # Mover la respuesta del modelo después del mensaje del usuario
    with st.chat_message(MODEL_ROLE, avatar=AI_AVATAR_ICON):
        try:
            message_placeholder = st.empty()
            typing_indicator = st.empty()
            typing_indicator.markdown("*Generando respuesta...*")
            
            response = state.send_message(enhanced_prompt)
            full_response = stream_response(response, message_placeholder, typing_indicator, STREAM_SETTINGS)
            
            if full_response:
                state.add_message(MODEL_ROLE, full_response, AI_AVATAR_ICON)
                if hasattr(state.chat, 'get_history'):
                    state.gemini_history = state.chat.get_history()
                else:
                    state.gemini_history = getattr(state.chat, 'history', [])
                state.save_chat_history()
                
        except Exception as e:
            st.error(f"Error en el streaming: {str(e)}")
            return

def handle_chat_title(prompt):
    """Maneja la lógica del título del chat"""
    if state.chat_id not in past_chats:
        temp_title = f'SesiónChat-{state.chat_id}'
        generated_title = state.generate_chat_title(prompt)
        state.chat_title = generated_title or temp_title
        past_chats[state.chat_id] = state.chat_title
    else:
        state.chat_title = past_chats[state.chat_id]
    if state.session_store:
        state.session_store.save_chat_index(state.user_id, past_chats)
    else:
        joblib.dump(past_chats, past_chats_path)

def detect_formula_selection(prompt):
    """Detecta si el usuario eligió una fórmula por nombre o por número."""
    normalized_prompt = prompt.lower().strip()
    formula_names = list(reel_formulas.keys())

    # Selección por número (1, 2, 3...)
    if normalized_prompt.isdigit():
        formula_index = int(normalized_prompt) - 1
        if 0 <= formula_index < len(formula_names):
            return formula_names[formula_index]

    # Selección por nombre parcial/completo
    for formula_name in formula_names:
        if formula_name.lower() in normalized_prompt:
            return formula_name

    return None

def get_user_context_for_formula(max_user_messages=6):
    """Recupera contexto reciente del usuario para rellenar la fórmula elegida."""
    recent_user_messages = [
        m['content'] for m in state.messages
        if m.get('role') == 'user'
    ][-max_user_messages:]
    return "\n".join(f"- {message}" for message in recent_user_messages)

def build_formula_prompt(formula_name):
    """Construye un prompt estricto usando la fórmula del diccionario."""
    formula_data = reel_formulas[formula_name]
    formula_description = formula_data.get('description', '').strip()
    user_context = get_user_context_for_formula()

    return f"""
El usuario eligió explícitamente esta fórmula: "{formula_name}".

APLICA ESTRICTAMENTE la siguiente estructura:
{formula_description}

Contexto real del usuario (úsalo para personalizar el guion):
{user_context if user_context else '- Sin contexto previo suficiente.'}

Instrucciones obligatorias de salida:
1) Devuelve SOLO el texto final del Reel (sin encabezados ni etiquetas).
2) Respeta el orden y los pasos de la fórmula elegida.
3) Incluye un gancho potente y un cierre con llamado a la acción.
4) Que tenga longitud aproximada de 60 segundos al leer.
"""

def get_enhanced_prompt(prompt, is_example):
    """Genera el prompt mejorado según el tipo de mensaje"""
    selected_formula = detect_formula_selection(prompt)
    if selected_formula:
        st.session_state.selected_formula = selected_formula
        return build_formula_prompt(selected_formula)

    if is_greeting(prompt):
        return f"El usuario te ha saludado con '{prompt}'. Preséntate brevemente, explica qué es un Reel y por qué es importante, y haz las 3 preguntas iniciales para comenzar a crear el guion del Reel (audiencia ideal, producto/servicio, y llamado a la acción). Sé amigable, breve y toma la iniciativa como el experto que eres."
    elif is_example:
        return f"El usuario ha seleccionado un ejemplo: '{prompt}'. Responde de manera conversacional y sencilla, como si estuvieras hablando con un amigo. Evita tecnicismos innecesarios. Enfócate en dar información práctica que ayude al usuario a crear su Reel. Usa ejemplos concretos cuando sea posible. Termina tu respuesta con una pregunta que invite al usuario a compartir información sobre su negocio para poder ayudarle a crear su Reel personalizado."
    return prompt

def stream_response(response, message_placeholder, typing_indicator, stream_settings):
    """Maneja el streaming de la respuesta"""
    full_response = ''
    batch_size = max(1, int(stream_settings.get('batch_size', 24)))
    delay_seconds = max(0.0, float(stream_settings.get('delay_seconds', 0.0)))
    pending_chars = 0

    try:
        for chunk in response:
            if chunk.text:
                for ch in chunk.text:
                    full_response += ch
                    pending_chars += 1
                    if pending_chars >= batch_size:
                        if delay_seconds:
                            time.sleep(delay_seconds)
                        message_placeholder.markdown(full_response + '▌')
                        pending_chars = 0
    except Exception as e:
        st.error(f"Error en el streaming: {str(e)}")
        return ''

    if pending_chars > 0:
        if delay_seconds:
            time.sleep(delay_seconds)
        message_placeholder.markdown(full_response + '▌')

    typing_indicator.empty()
    message_placeholder.markdown(full_response)
    return full_response

# Función para cargar CSS personalizado
def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Intentar cargar el CSS personalizado con ruta absoluta para mayor seguridad
try:
    css_path = os.path.join(os.path.dirname(__file__), 'static', 'css', 'style.css')
    load_css(css_path)
except Exception as e:
    print(f"Error al cargar CSS: {e}")
    # Si el archivo no existe, crear un estilo básico en línea
    st.markdown("""
    <style>
    .robocopy-title {
        color: white !important;
        font-weight: bold;
        font-size: clamp(2.5em, 5vw, 4em);
        line-height: 1.2;
    }
    </style>
    """, unsafe_allow_html=True)

# Función de utilidad para mostrar la carátula inicial
def display_initial_header():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Centrar la imagen
        st.markdown("""
            <style>
                div.stImage {
                    text-align: center;
                    display: block;
                    margin-left: auto;
                    margin-right: auto;
                }
            </style>
        """, unsafe_allow_html=True)
        st.image("robocopy_logo.png", width=300, use_container_width=True)
        
        # Título con diseño responsivo (eliminado el símbolo ∞)
        st.markdown("""
            <div style='text-align: center; margin-top: -35px; width: 100%;'>
                <h1 class='robocopy-title' style='width: 100%; text-align: center; color: white !important; font-size: clamp(2.5em, 5vw, 4em); line-height: 1.2;'>Reel Creator</h1>
            </div>
        """, unsafe_allow_html=True)
        
        # Subtítulo con margen superior ajustado a -30px
        st.markdown("""
            <div style='text-align: center; width: 100%;'>
                <p style='font-size: 16px; color: white; width: 100%; text-align: center; margin-top: -20px;'>By Jesús Cabrera</p>
            </div>
        """, unsafe_allow_html=True)
    
    # Descripción con fondo eliminado y margen superior ajustado a -20px
    st.markdown("""
        <div style='text-align: center; width: 100%;'>
            <p style='font-size: 16px; background-color: transparent; padding: 12px; border-radius: 8px; margin-top: -20px; color: white; width: 100%; text-align: center;'>
                🎥 Experto en crear Reels virales que convierten visualizaciones en clientes
            </p>
        </div>
    """, unsafe_allow_html=True)

# Función para mostrar ejemplos de preguntas
def display_examples():
    ejemplos = [
        {"texto": "¿Cómo crear un Reel efectivo? 🎥", "prompt": "Explícame cómo puedo crear un Reel efectivo que enganche a mi audiencia desde el primer segundo"},
        {"texto": "Ideas para Reels de mi negocio 💡", "prompt": "Necesito ideas creativas para crear Reels que promocionen mi negocio y productos"},
        {"texto": "Estructura de un buen Reel ✨", "prompt": "¿Cuál es la mejor estructura para crear un Reel que mantenga la atención y genere conversiones?"},
        {"texto": "¿Qué fórmula de Reel usar? 🤔", "prompt": "Ayúdame a elegir la fórmula más adecuada para mi Reel según mi tipo de negocio y objetivo"}
    ]

    # Crear los botones de ejemplo
    cols = st.columns(4)
    for idx, ejemplo in enumerate(ejemplos):
        with cols[idx]:
            if st.button(ejemplo["texto"], key=f"ejemplo_{idx}", help=ejemplo["prompt"]):
                st.session_state.pending_example_prompt = ejemplo["prompt"]
                st.session_state.hide_initial_menu = True
                st.rerun()

# Cargar variables de entorno
load_dotenv()
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    st.error("Falta la variable de entorno GOOGLE_API_KEY. Configúrala para continuar.")
    st.stop()

# Configuración de la aplicación
new_chat_id = f'{time.time()}'
MODEL_ROLE = 'ai'
AI_AVATAR_ICON = '🤖'  # Cambia el emoji por uno de robot para coincidir con tu logo
USER_AVATAR_ICON = '👤'  # Añade un avatar para el usuario

# Resolver usuario actual (Firebase Auth token -> uid, fallback local)
firebase_store = FirebaseSessionStore.from_env()
id_token = st.query_params.get("token")
firebase_uid = None
if firebase_store and id_token:
    firebase_uid = firebase_store.verify_id_token(id_token)
state.set_storage(firebase_uid or state.user_id, firebase_store)

user_data_dir = f'{DATA_DIR}/users/{state.user_id}'
past_chats_path = f'{user_data_dir}/past_chats_list'

# Crear carpeta de datos si no existe
try:
    os.makedirs(user_data_dir, exist_ok=True)
except OSError:
    pass

# Cargar chats anteriores
if state.session_store:
    past_chats = state.session_store.load_chat_index(state.user_id)
else:
    try:
        past_chats = joblib.load(past_chats_path)
    except (FileNotFoundError, EOFError):
        past_chats = {}

# Sidebar para seleccionar chats anteriores
with st.sidebar:
    st.write('# Chats Anteriores')

    if state.chat_id is None:
        state.chat_id = st.selectbox(
            label='Selecciona un chat anterior',
            options=[new_chat_id] + list(past_chats.keys()),
            format_func=lambda x: past_chats.get(x, 'Nuevo Chat'),
            placeholder='_',
        )
    else:
        # This will happen the first time AI response comes in
        state.chat_id = st.selectbox(
            label='Selecciona un chat anterior',
            options=[new_chat_id, state.chat_id] + list(past_chats.keys()),
            index=1,
            format_func=lambda x: past_chats.get(x, 'Nuevo Chat' if x != state.chat_id else state.chat_title),
            placeholder='_',
        )
    # Save new chats after a message has been sent to AI
    state.chat_title = f'SesiónChat-{state.chat_id}'

# Cargar historial del chat
state.load_chat_history()

# Inicializar el modelo y el chat
system_prompt = get_unified_reel_prompt()
state.initialize_model(DEFAULT_GEMINI_MODEL, api_key=GOOGLE_API_KEY)
state.initialize_chat(system_instruction=system_prompt)  # Siempre inicializar el chat después del modelo

# Mostrar mensajes del historial
for message in state.messages:
    with st.chat_message(
        name=message['role'],
        avatar=message.get('avatar'),
    ):
        st.markdown(message['content'])

# Capturar entrada del usuario antes de renderizar el menú inicial
user_prompt = st.chat_input('Describe tu audiencia y el objetivo de tu Reel...')

if 'pending_example_prompt' not in st.session_state:
    st.session_state.pending_example_prompt = None

if 'hide_initial_menu' not in st.session_state:
    st.session_state.hide_initial_menu = False

if state.has_messages():
    st.session_state.hide_initial_menu = True

# Renderizar menú inicial en un contenedor limpiable
initial_menu_container = st.container()
if (
    not st.session_state.hide_initial_menu
    and not state.has_messages()
    and not user_prompt
    and not st.session_state.pending_example_prompt
):
    with initial_menu_container:
        display_initial_header()
        display_examples()

# Procesar entrada del usuario (oculta el menú inmediatamente)
if user_prompt:
    st.session_state.hide_initial_menu = True
    initial_menu_container.empty()
    process_message(user_prompt, is_example=False)

# Procesar ejemplo seleccionado (oculta el menú inmediatamente)
if st.session_state.pending_example_prompt:
    initial_menu_container.empty()
    process_message(st.session_state.pending_example_prompt, is_example=True)
    st.session_state.pending_example_prompt = None
