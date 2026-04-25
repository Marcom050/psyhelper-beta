import streamlit as st
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
import os
import pickle
import hashlib

st.set_page_config(page_title="PsyHelper", page_icon="🧠", layout="centered")

st.markdown('<div style="background: linear-gradient(90deg, #4338ca, #6366f1); color: white; padding: 14px; border-radius: 10px; text-align: center; margin-bottom: 20px; font-weight: 600;">🔬 PsyHelper - VERSIONE BETA<br>Stiamo testando l’app. Il tuo feedback è prezioso!</div>', unsafe_allow_html=True)

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    st.error("⚠️ API Key non configurata!")
    st.stop()

llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.55, api_key=GROQ_API_KEY)

USERS_DIR = os.path.expanduser("~/psyhelper_data/users")
os.makedirs(USERS_DIR, exist_ok=True)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def user_exists(username):
    return os.path.exists(f"{USERS_DIR}/{username}")

def create_user(username, password):
    user_dir = f"{USERS_DIR}/{username}"
    os.makedirs(user_dir, exist_ok=True)
    with open(f"{user_dir}/password.txt", "w") as f:
        f.write(hash_password(password))
    with open(f"{user_dir}/profile.pkl", "wb") as f:
        pickle.dump({}, f)
    with open(f"{user_dir}/messages.pkl", "wb") as f:
        pickle.dump([], f)

def verify_password(username, password):
    try:
        with open(f"{USERS_DIR}/{username}/password.txt", "r") as f:
            return f.read() == hash_password(password)
    except:
        return False

def load_user_data(username):
    user_dir = f"{USERS_DIR}/{username}"
    try:
        with open(f"{user_dir}/profile.pkl", "rb") as f:
            st.session_state.profile = pickle.load(f)
        with open(f"{user_dir}/messages.pkl", "rb") as f:
            st.session_state.messages = pickle.load(f)
    except:
        st.session_state.profile = {}
        st.session_state.messages = []

def save_user_data(username):
    user_dir = f"{USERS_DIR}/{username}"
    with open(f"{user_dir}/profile.pkl", "wb") as f:
        pickle.dump(st.session_state.profile, f)
    with open(f"{user_dir}/messages.pkl", "wb") as f:
        pickle.dump(st.session_state.messages, f)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "show_mindfulness" not in st.session_state:
    st.session_state.show_mindfulness = False

if not st.session_state.logged_in:
    st.title("🧠 PsyHelper - Accesso")
    tab1, tab2 = st.tabs(["Login", "Registrati"])
    with tab1:
        with st.form("login"):
            username = st.text_input("Nome utente")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Accedi", use_container_width=True):
                if user_exists(username) and verify_password(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    load_user_data(username)
                    st.rerun()
                else:
                    st.error("Nome utente o password errati")
    with tab2:
        with st.form("signup"):
            new_username = st.text_input("Scegli un nome utente")
            new_password = st.text_input("Scegli una password", type="password")
            confirm_password = st.text_input("Conferma password", type="password")
            if st.form_submit_button("Registrati", use_container_width=True):
                if new_password != confirm_password:
                    st.error("Le password non coincidono")
                elif user_exists(new_username):
                    st.error("Nome utente già esistente")
                elif len(new_username) < 3:
                    st.error("Il nome utente deve avere almeno 3 caratteri")
                else:
                    create_user(new_username, new_password)
                    st.success("Registrazione completata! Ora effettua il login.")
    st.stop()

st.title("🧠 PsyHelper")
st.markdown(f"<p class='subtitle'>Ciao {st.session_state.username}, sono qui per aiutarti</p>", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("Scrivi qui cosa stai provando..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.markdown(user_input)
    with st.chat_message("assistant"):
        with st.spinner("Sto pensando..."):
            reply = get_response(user_input)
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
    save_user_data(st.session_state.username)

st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🧘 Mindfulness"): st.session_state.show_mindfulness = not st.session_state.show_mindfulness
with col2:
    if st.button("🔄 Nuova conversazione"):
        st.session_state.messages = []
        save_user_data(st.session_state.username)
        st.rerun()
with col3:
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.rerun()

if st.session_state.show_mindfulness:
    st.subheader("🧘 Esercizi di Mindfulness")
    st.markdown('<div class="mindfulness-box"><strong>Respirazione 4-7-8</strong><br>Calma ansia velocemente</div>', unsafe_allow_html=True)
    st.markdown('<div class="mindfulness-box"><strong>Grounding 5-4-3-2-1</strong><br>Riporta la mente al presente</div>', unsafe_allow_html=True)
