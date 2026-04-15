import time
import os
import joblib
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
from system_prompts import get_unified_reel_prompt  # Cambiar de get_unified_puv_prompt a get_unified_reel_prompt
from session_state import (
    SessionState,
    DEFAULT_GEMINI_MODEL,
    DATA_DIR,
    PAST_CHATS_LIST_PATH,
)

# Inicializar el estado de la sesión
state = SessionState()
STREAM_PRESETS = {
    'Rápido': {'batch_size': 24, 'delay_seconds': 0.0},
    'Cinemático': {'batch_size': 1, 'delay_seconds': 0.01},
}

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
            stream_mode = st.session_state.get('stream_mode', 'Rápido')
            stream_settings = STREAM_PRESETS.get(stream_mode, STREAM_PRESETS['Rápido'])
            full_response = stream_response(response, message_placeholder, typing_indicator, stream_settings)
            
            if full_response:
                state.add_message(MODEL_ROLE, full_response, AI_AVATAR_ICON)
                state.gemini_history = state.chat.history
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
    joblib.dump(past_chats, PAST_CHATS_LIST_PATH)

def get_enhanced_prompt(prompt, is_example):
    """Genera el prompt mejorado según el tipo de mensaje"""
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
                state.prompt = ejemplo["prompt"]
                st.rerun()

# Cargar variables de entorno
load_dotenv()
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    st.error("Falta la variable de entorno GOOGLE_API_KEY. Configúrala para continuar.")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)

# Configuración de la aplicación
new_chat_id = f'{time.time()}'
MODEL_ROLE = 'ai'
AI_AVATAR_ICON = '🤖'  # Cambia el emoji por uno de robot para coincidir con tu logo
USER_AVATAR_ICON = '👤'  # Añade un avatar para el usuario

# Crear carpeta de datos si no existe
try:
    os.mkdir(DATA_DIR)
except FileExistsError:
    # data/ folder already exists
    pass

# Cargar chats anteriores
try:
    past_chats: dict = joblib.load(PAST_CHATS_LIST_PATH)
except (FileNotFoundError, EOFError):
    past_chats = {}

# Sidebar para seleccionar chats anteriores
with st.sidebar:
    st.write('# Chats Anteriores')
    st.write('### Velocidad de respuesta')
    st.session_state.stream_mode = st.radio(
        label='Modo de streaming',
        options=list(STREAM_PRESETS.keys()),
        index=0 if st.session_state.get('stream_mode', 'Rápido') == 'Rápido' else 1,
        horizontal=True,
        label_visibility='collapsed',
    )

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
state.initialize_model(DEFAULT_GEMINI_MODEL)
state.initialize_chat()  # Siempre inicializar el chat después del modelo

# Mostrar mensajes del historial
for message in state.messages:
    with st.chat_message(
        name=message['role'],
        avatar=message.get('avatar'),
    ):
        st.markdown(message['content'])

# Mensaje inicial del sistema si es un chat nuevo
if not state.has_messages():
    # Mostrar la carátula inicial con el logo centrado
    display_initial_header()
    
    # Mostrar los ejemplos
    display_examples()

    # Inicializar el chat con el prompt unificado
    system_prompt = get_unified_reel_prompt()  # Cambiar de get_unified_puv_prompt a get_unified_reel_prompt
    if state.chat is not None:  # Verificación adicional de seguridad
        state.chat.send_message(system_prompt)
    else:
        st.error("Error: No se pudo inicializar el chat correctamente.")

# Procesar entrada del usuario
if prompt := st.chat_input('Describe tu audiencia y el objetivo de tu Reel...'):
    process_message(prompt, is_example=False)

# Procesar ejemplos seleccionados
if state.has_prompt():
    prompt = state.prompt
    process_message(prompt, is_example=True)
    # Limpiar el prompt
    state.clear_prompt()
