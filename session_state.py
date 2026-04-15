import streamlit as st
import joblib
import os
import uuid
from google import genai
from google.genai import types

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

        if 'client' not in st.session_state:
            st.session_state.client = None
            
        if 'chat' not in st.session_state:
            st.session_state.chat = None
            
        if 'prompt' not in st.session_state:
            st.session_state.prompt = None

        if 'system_instruction' not in st.session_state:
            st.session_state.system_instruction = None

        if 'user_id' not in st.session_state:
            st.session_state.user_id = f'local-{uuid.uuid4()}'

        if 'session_store' not in st.session_state:
            st.session_state.session_store = None
    
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
    def client(self):
        return st.session_state.client

    @client.setter
    def client(self, value):
        st.session_state.client = value
    
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

    @property
    def system_instruction(self):
        return st.session_state.system_instruction

    @system_instruction.setter
    def system_instruction(self, value):
        st.session_state.system_instruction = value

    @property
    def user_id(self):
        return st.session_state.user_id

    @user_id.setter
    def user_id(self, value):
        st.session_state.user_id = value

    @property
    def session_store(self):
        return st.session_state.session_store

    @session_store.setter
    def session_store(self, value):
        st.session_state.session_store = value
    
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

    def set_storage(self, user_id, session_store=None):
        """Configura el usuario actual y el store opcional (Firebase)."""
        self.user_id = user_id
        self.session_store = session_store
    
    def initialize_model(self, model_name=None, api_key=None):
        """Inicializa el modelo de IA"""
        if model_name is None:
            model_name = DEFAULT_GEMINI_MODEL
        if api_key is None:
            api_key = os.environ.get('GOOGLE_API_KEY')
        self.client = genai.Client(api_key=api_key)
        self.model = model_name
    
    def initialize_chat(self, history=None, system_instruction=None):
        """Inicializa el chat con el modelo"""
        if history is None:
            history = self.gemini_history
        if system_instruction is None:
            system_instruction = self.system_instruction
        else:
            self.system_instruction = system_instruction
        
        # Asegurar que el modelo está inicializado
        if self.model is None or self.client is None:
            self.initialize_model()

        chat_kwargs = {'model': self.model}
        if history:
            chat_kwargs['history'] = history
        if system_instruction:
            chat_kwargs['config'] = types.GenerateContentConfig(
                system_instruction=system_instruction
            )

        # Inicializar chat con el SDK moderno
        self.chat = self.client.chats.create(**chat_kwargs)
        
        # Verificar que el chat se inicializó correctamente
        if self.chat is None:
            raise ValueError("Error al inicializar el chat")
    
    def send_message(self, prompt, stream=True):
        """Método unificado para enviar mensajes y mantener el streaming"""
        try:
            if self.chat is None:
                self.initialize_chat()
                
            if stream:
                return self.chat.send_message_stream(prompt)
            return self.chat.send_message(prompt)
        except Exception as e:
            print(f"Error al enviar mensaje: {e}")
            # Reintentar una vez si hay error
            self.initialize_chat()
            if stream:
                return self.chat.send_message_stream(prompt)
            return self.chat.send_message(prompt)
    
    def generate_chat_title(self, prompt, model_name=None):
        """Genera un título para el chat basado en el primer mensaje"""
        try:
            if model_name is None:
                model_name = DEFAULT_GEMINI_MODEL
            if self.client is None:
                self.client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))
            title_response = self.client.models.generate_content(
                model=model_name,
                contents=(
                    "Genera un título natural y humano en español (3 a 6 palabras) "
                    "que resuma esta consulta. No uses separadores tipo '|', no uses etiquetas, "
                    "no uses comillas y evita formato robótico. Devuelve solo el título final: "
                    f"'{prompt}'"
                )
            )
            cleaned_title = " ".join(
                title_response.text.strip().replace('"', '').replace('|', ' ').split()
            )
            return " ".join(cleaned_title.split()[:6])
        except Exception as e:
            print(f"Error al generar título: {e}")
            return None
    
    def save_chat_history(self, chat_id=None):
        """Guarda el historial del chat"""
        if chat_id is None:
            chat_id = self.chat_id
        
        if self.session_store:
            self.session_store.save_chat_history(self.user_id, chat_id, self.messages, self.gemini_history)
            return

        os.makedirs(self._user_data_dir(), exist_ok=True)
        joblib.dump(self.messages, self._st_messages_path(chat_id))
        joblib.dump(self.gemini_history, self._gemini_messages_path(chat_id))
    
    def load_chat_history(self, chat_id=None):
        """Carga el historial del chat"""
        if chat_id is None:
            chat_id = self.chat_id
        
        try:
            if self.session_store:
                messages, gemini_history = self.session_store.load_chat_history(self.user_id, chat_id)
                if messages is not None and gemini_history is not None:
                    self.messages = messages
                    self.gemini_history = gemini_history
                    return True
                self.messages = []
                self.gemini_history = []
                return False

            self.messages = joblib.load(self._st_messages_path(chat_id))
            self.gemini_history = joblib.load(self._gemini_messages_path(chat_id))
            return True
        except (FileNotFoundError, EOFError):
            self.messages = []
            self.gemini_history = []
            return False

    def _st_messages_path(self, chat_id):
        return f'{self._user_data_dir()}/{chat_id}-st_messages'

    def _gemini_messages_path(self, chat_id):
        return f'{self._user_data_dir()}/{chat_id}-gemini_messages'

    def _user_data_dir(self):
        return f'{DATA_DIR}/users/{self.user_id}'
    
    def has_messages(self):
        """Verifica si hay mensajes en el historial"""
        return len(self.messages) > 0
    
    def has_prompt(self):
        """Verifica si hay un prompt en el estado de la sesión"""
        return self.prompt is not None and self.prompt.strip() != ""
