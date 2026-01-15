import streamlit as st
import bcrypt
import database as db
import time

# ==========================================
# 1. FUNCIONES DE LÓGICA (Funcionan en TODO)
# ==========================================

def hash_password(password):
    """Genera un hash seguro. Funciona en prueba.py y app.py."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """Verifica la contraseña. Funciona en prueba.py y app.py."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

# ==========================================
# 2. FUNCIONES DE INTERFAZ (Solo para Streamlit)
# ==========================================

def init_session():
    """Inicializa variables en app.py."""
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'user_info' not in st.session_state:
        st.session_state['user_info'] = None

def show_login():
    """Muestra el formulario en app.py."""
    st.title("🔐 Acceso al Sistema")
    with st.form("login_form"):
        email = st.text_input("Correo").lower().strip()
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            # Usamos %s para que siempre funcione con Postgres
            user_data = db.run_query("SELECT * FROM usuarios WHERE email=%s", (email,), return_data=True)
            
            if not user_data.empty:
                # Sacamos el hash de la base de datos
                stored_hash = user_data.iloc[0]['password_hash']
                
                if stored_hash and check_password(password, stored_hash):
                    st.session_state['user_info'] = user_data.iloc[0].to_dict()
                    st.session_state['logged_in'] = True
                    st.success("¡Acceso correcto!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
            else:
                st.error("Usuario no encontrado")

def logout():
    """Cierra sesión en app.py."""
    st.session_state['logged_in'] = False
    st.session_state['user_info'] = None
    st.rerun()