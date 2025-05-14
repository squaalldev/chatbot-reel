import time
import os
import joblib
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
from reels_formulas import reels_formulas
from system_prompts import get_reels_script_prompt
from session_state import SessionState

# Configuración de la página - DEBE SER LA PRIMERA LLAMADA A STREAMLIT
st.set_page_config(
    page_title="RoboCopy - Reels Creator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cargar variables de entorno
load_dotenv()
GOOGLE_API_KEY=os.environ.get('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

# Configuración de la aplicación
new_chat_id = f'{time.time()}'
MODEL_ROLE = 'model'
USER_AVATAR_ICON = '👤'
AI_AVATAR_ICON = '🤖'

# Inicializar el estado de la sesión
state = SessionState()

# Crear directorio de datos si no existe
os.makedirs('data', exist_ok=True)

# Cargar historial de chats pasados
try:
    past_chats = joblib.load('data/past_chats_list')
except:
    past_chats = {}

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
            full_response = stream_response(response, message_placeholder, typing_indicator)
            
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
    joblib.dump(past_chats, 'data/past_chats_list')

def get_enhanced_prompt(prompt, is_example):
    """Genera el prompt mejorado según el tipo de mensaje"""
    if is_greeting(prompt):
        return f"El usuario te ha saludado con '{prompt}'. Preséntate brevemente (máximo 2 líneas), explica qué es un guion de Reel en 1 línea, y haz SOLO 1 pregunta inicial para comenzar a crear el guion. Sé extremadamente conciso."
    elif is_example:
        return f"El usuario ha seleccionado un ejemplo: '{prompt}'. Responde de manera breve y directa en máximo 3-4 líneas. Evita explicaciones largas. Termina con una única pregunta concreta."
    else:
        # Para conversaciones normales, añadir instrucción de brevedad
        return prompt + " [IMPORTANTE: Responde de forma breve y concisa. Máximo 3-5 líneas. Si necesitas hacer preguntas, limítalas a 1-2 preguntas clave sobre el nicho/tema y objetivo del Reel. Recuerda que estamos creando guiones para Reels de Instagram/Facebook (videos cortos de 15-60 segundos), NO para películas o teatro.]"
    return prompt

def process_model_response(enhanced_prompt):
    """Procesa la respuesta del modelo"""
    with st.chat_message(MODEL_ROLE, avatar=AI_AVATAR_ICON):
        try:
            message_placeholder = st.empty()
            typing_indicator = st.empty()
            typing_indicator.markdown("*Generando respuesta...*")
            
            response = state.send_message(enhanced_prompt)
            full_response = stream_response(response, message_placeholder, typing_indicator)
            
            # Actualizar historial
            state.add_message(role=MODEL_ROLE, content=full_response, avatar=AI_AVATAR_ICON)
            state.gemini_history = state.chat.history
            state.save_chat_history()
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

def stream_response(response, message_placeholder, typing_indicator):
    """Maneja el streaming de la respuesta"""
    full_response = ''
    try:
        for chunk in response:
            if chunk.text:
                for ch in chunk.text:
                    full_response += ch
                    time.sleep(0.01)
                    typing_indicator.markdown("*Generando respuesta...*")
                    message_placeholder.markdown(full_response + '▌')
    except Exception as e:
        st.error(f"Error en el streaming: {str(e)}")
        return ''
    
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
        
        # Título con diseño responsivo
        st.markdown("""
            <div style='text-align: center; margin-top: -35px; width: 100%;'>
                <h1 class='robocopy-title' style='width: 100%; text-align: center; color: white !important; font-size: clamp(2.5em, 5vw, 4em); line-height: 1.2;'>Reels Creator</h1>
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
                🎬 Experto en crear guiones de Reels virales para Instagram y Facebook
            </p>
        </div>
    """, unsafe_allow_html=True)

# Función para mostrar ejemplos de preguntas
def display_examples():
    ejemplos = [
        {"texto": "¿Qué es un Reel efectivo? 🎬", "prompt": "Explícame qué es un Reel efectivo y por qué es importante para mi estrategia de redes sociales"},
        {"texto": "¿Cómo puedo crear mi guion de Reel? 📝", "prompt": "Guíame paso a paso en el proceso de crear un guion de Reel efectivo"},
        {"texto": "¿Qué elementos debe tener mi Reel? ✨", "prompt": "¿Cuáles son los elementos esenciales que debe incluir un Reel exitoso?"},
        {"texto": "¿Cuál es la mejor fórmula para mi caso? 🤔", "prompt": "Ayúdame a elegir la fórmula más adecuada para mi guion de Reel según mi nicho"}
    ]

    # Crear los botones de ejemplo
    cols = st.columns(4)
    for idx, ejemplo in enumerate(ejemplos):
        with cols[idx]:
            if st.button(ejemplo["texto"], key=f"ejemplo_{idx}", help=ejemplo["prompt"]):
                state.prompt = ejemplo["prompt"]
                st.rerun()

# Inicializar el sistema de prompt
system_prompt = get_reels_script_prompt()

# Inicializar el modelo si no está inicializado
if state.model is None:
    state.initialize_model()
    state.initialize_chat()

# Sidebar para navegación y opciones
with st.sidebar:
    st.markdown("## 🎬 RoboCopy - Reels Creator")
    st.markdown("---")
    
    # Botón para nueva conversación
    if st.button("🆕 Nueva Conversación", use_container_width=True):
        state.chat_id = new_chat_id
        state.messages = []
        state.gemini_history = []
        state.initialize_chat()
        st.rerun()
    
    # Selector de chats pasados
    st.markdown("### 💬 Conversaciones Pasadas")
    
    # Mostrar chats pasados en orden inverso (más recientes primero)
    past_chat_ids = list(past_chats.keys())
    past_chat_ids.sort(reverse=True)
    
    for chat_id in past_chat_ids:
        chat_title = past_chats[chat_id]
        if st.button(f"📝 {chat_title}", key=f"chat_{chat_id}", use_container_width=True):
            state.chat_id = chat_id
            state.load_chat_history(chat_id)
            state.initialize_chat(state.gemini_history)
            st.rerun()
    
    # Información adicional
    st.markdown("---")
    st.markdown("### ℹ️ Información")
    st.markdown("""
    **RoboCopy - Reels Creator** te ayuda a crear guiones efectivos para tus Reels de Instagram y Facebook.
    
    Simplemente describe tu nicho, audiencia y objetivo, y te ayudaremos a crear un guion optimizado para generar engagement.
    """)

# Contenido principal
if state.chat_id is None:
    state.chat_id = new_chat_id

# Mostrar la carátula inicial
display_initial_header()

# Mostrar ejemplos de preguntas
st.markdown("### 💡 Ejemplos de preguntas para comenzar:")
display_examples()

# Mostrar historial de mensajes
for message in state.messages:
    with st.chat_message(message["role"], avatar=message.get("avatar")):
        st.markdown(message["content"])

# Procesar el prompt si existe
if state.has_prompt():
    prompt = state.prompt
    state.clear_prompt()
    process_message(prompt, is_example=True)

# Input para nuevo mensaje
user_input = st.chat_input("Escribe tu mensaje aquí...")
if user_input:
    process_message(user_input)