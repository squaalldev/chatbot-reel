import streamlit as st
import joblib
import google.generativeai as genai

DEFAULT_GEMINI_MODEL = 'gemini-3.1-flash-lite-preview'
DATA_DIR = 'data'
PAST_CHATS_LIST_PATH = f'{DATA_DIR}/past_chats_list'

class SessionState:
    """
    Clase para gestionar el estado de la sesión de Streamlit de manera centralizada.
    Encapsula todas las operaciones relacionadas con st.session_state.
    """
    
    def __init__(self):
        # Inicializar valores por defecto si no existen
        if 'chat_id' not in st.session_state:
            st.session_state.chat_id = None
        
        if 'chat_title' not in st.session_state:
            st.session_state.chat_title = None
            
        if 'messages' not in st.session_state:
            st.session_state.messages = []
            
        if 'gemini_history' not in st.session_state:
            st.session_state.gemini_history = []
            
        if 'model' not in st.session_state:
            st.session_state.model = None
            
        if 'chat' not in st.session_state:
            st.session_state.chat = None
            
        if 'prompt' not in st.session_state:
            st.session_state.prompt = None
    
    # Getters y setters para cada propiedad
    @property
    def chat_id(self):
        return st.session_state.chat_id
    
    @chat_id.setter
    def chat_id(self, value):
        st.session_state.chat_id = value
    
    @property
    def chat_title(self):
        return st.session_state.chat_title
    
    @chat_title.setter
    def chat_title(self, value):
        st.session_state.chat_title = value
    
    @property
    def messages(self):
        return st.session_state.messages
    
    @messages.setter
    def messages(self, value):
        st.session_state.messages = value
    
    @property
    def gemini_history(self):
        return st.session_state.gemini_history
    
    @gemini_history.setter
    def gemini_history(self, value):
        st.session_state.gemini_history = value
    
    @property
    def model(self):
        return st.session_state.model
    
    @model.setter
    def model(self, value):
        st.session_state.model = value
    
    @property
    def chat(self):
        return st.session_state.chat
    
    @chat.setter
    def chat(self, value):
        st.session_state.chat = value
    
    @property
    def prompt(self):
        return st.session_state.prompt
    
    @prompt.setter
    def prompt(self, value):
        st.session_state.prompt = value
    
    # Métodos de utilidad
    def add_message(self, role, content, avatar=None):
        """Añade un mensaje al historial"""
        message = {
            'role': role,
            'content': content,
        }
        if avatar:
            message['avatar'] = avatar
        self.messages.append(message)
    
    def clear_prompt(self):
        """Limpia el prompt del estado de la sesión"""
        self.prompt = None
    
    def initialize_model(self, model_name=None):
        """Inicializa el modelo de IA"""
        if model_name is None:
            model_name = DEFAULT_GEMINI_MODEL
        self.model = genai.GenerativeModel(model_name)
    
    def initialize_chat(self, history=None):
        """Inicializa el chat con el modelo"""
        if history is None:
            history = self.gemini_history
        
        # Asegurar que el modelo está inicializado
        if self.model is None:
            self.initialize_model()
            
        # Inicializar el chat sin generation_config
        self.chat = self.model.start_chat(history=history)
        
        # Verificar que el chat se inicializó correctamente
        if self.chat is None:
            raise ValueError("Error al inicializar el chat")
    
    def send_message(self, prompt, stream=True):
        """Método unificado para enviar mensajes y mantener el streaming"""
        try:
            if self.chat is None:
                self.initialize_chat()
                
            return self.chat.send_message(
                prompt,
                stream=stream,
                generation_config={
                    "temperature": 0.9
                }
            )
        except Exception as e:
            print(f"Error al enviar mensaje: {e}")
            # Reintentar una vez si hay error
            self.initialize_chat()
            return self.chat.send_message(
                prompt,
                stream=stream,
                generation_config={
                    "temperature": 0.9
                }
            )
    
    def generate_chat_title(self, prompt, model_name=None):
        """Genera un título para el chat basado en el primer mensaje"""
        try:
            if model_name is None:
                model_name = DEFAULT_GEMINI_MODEL
            title_generator = genai.GenerativeModel(model_name)
            title_response = title_generator.generate_content(
                f"Genera un título corto (máximo 5 palabras) que describa de qué trata esta consulta, sin usar comillas ni puntuación: '{prompt}'")
            return title_response.text.strip()
        except Exception as e:
            print(f"Error al generar título: {e}")
            return None
    
    def save_chat_history(self, chat_id=None):
        """Guarda el historial del chat"""
        if chat_id is None:
            chat_id = self.chat_id
        
        joblib.dump(self.messages, self._st_messages_path(chat_id))
        joblib.dump(self.gemini_history, self._gemini_messages_path(chat_id))
    
    def load_chat_history(self, chat_id=None):
        """Carga el historial del chat"""
        if chat_id is None:
            chat_id = self.chat_id
        
        try:
            self.messages = joblib.load(self._st_messages_path(chat_id))
            self.gemini_history = joblib.load(self._gemini_messages_path(chat_id))
            return True
        except (FileNotFoundError, EOFError):
            self.messages = []
            self.gemini_history = []
            return False

    def _st_messages_path(self, chat_id):
        return f'{DATA_DIR}/{chat_id}-st_messages'

    def _gemini_messages_path(self, chat_id):
        return f'{DATA_DIR}/{chat_id}-gemini_messages'
    
    def has_messages(self):
        """Verifica si hay mensajes en el historial"""
        return len(self.messages) > 0
    
    def has_prompt(self):
        """Verifica si hay un prompt en el estado de la sesión"""
        return self.prompt is not None and self.prompt.strip() != ""
