import hashlib
import os
import pickle
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_groq import ChatGroq

st.set_page_config(page_title="PsyHelper", page_icon="🧠", layout="centered")

# =============================================
# TITOLO E DISCLAIMER - INIZIO PAGINA
# =============================================
st.title("🧠 PsyHelper")

st.markdown("""
<div style="background-color: #1f2937; padding: 16px; border-radius: 10px; border: 1px solid #6366f1; margin-bottom: 30px;">
    <strong>⚠️ Disclaimer:</strong> PsyHelper è uno strumento di supporto e <strong>non sostituisce</strong> una terapia professionale.<br>
    In caso di difficoltà gravi consulta un professionista della salute mentale o i servizi di emergenza se sei in pericolo immediato.<br><br>
    <strong>Privacy:</strong> Tutte le tue conversazioni e schede sono private e salvate solo sul tuo account.
</div>
""", unsafe_allow_html=True)

# Google Analytics
st.markdown("""
<script async src="https://www.googletagmanager.com/gtag/js?id=G-KWR24JLV0Y"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-KWR24JLV0Y');
</script>
""", unsafe_allow_html=True)

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    st.error("⚠️ API Key non configurata!")
    st.stop()

llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.50, api_key=GROQ_API_KEY)

USERS_DIR = os.path.expanduser("~/psyhelper_data/users")
os.makedirs(USERS_DIR, exist_ok=True)

MOOD_OPTIONS = ["Sereno", "Ansioso", "Triste", "Irritabile", "Sovraccarico", "Speranzoso", "Altro"]
SENSATION_OPTIONS = [
    "Tensione muscolare",
    "Nodo allo stomaco",
    "Respiro corto",
    "Tachicardia",
    "Stanchezza",
    "Irrequietezza",
    "Testa pesante",
    "Calore/freddo",
]
MINDFULNESS_EXERCISES = {
    "Respiro 4-6": {
        "durata": "3-5 minuti",
        "obiettivo": "Ridurre attivazione fisiologica e ansia.",
        "passi": [
            "Appoggia i piedi a terra e nota tre punti di contatto con la sedia.",
            "Inspira dal naso contando fino a 4.",
            "Espira lentamente contando fino a 6, come se sgonfiassi un palloncino.",
            "Ripeti per 10 cicli e riporta l'attenzione al respiro ogni volta che la mente vaga.",
        ],
        "riflessione": "Quale pensiero automatico si è ammorbidito anche solo dell'1%?",
    },
    "Grounding 5-4-3-2-1": {
        "durata": "5 minuti",
        "obiettivo": "Ancorarsi al presente durante stress o rimuginio.",
        "passi": [
            "Nomina 5 cose che vedi.",
            "Nomina 4 sensazioni fisiche che percepisci.",
            "Nomina 3 suoni che senti.",
            "Nomina 2 odori o sapori presenti.",
            "Concludi con 1 azione utile e realistica per i prossimi 10 minuti.",
        ],
        "riflessione": "Che differenza noti tra minaccia immaginata e situazione presente?",
    },
    "Defusione dal pensiero": {
        "durata": "4 minuti",
        "obiettivo": "Osservare i pensieri senza trattarli come fatti.",
        "passi": [
            "Scrivi o pronuncia un pensiero stressante.",
            "Aggiungi davanti: 'Sto avendo il pensiero che...'.",
            "Ripetilo lentamente tre volte e nota cosa cambia nel corpo.",
            "Chiediti: 'Quale comportamento coerente con i miei valori posso fare ora?'.",
        ],
        "riflessione": "Quanto credibile sembra il pensiero da 0 a 100 dopo l'esercizio?",
    },
}


def scroll_to_top():
    st.html(
        """
        <script>
            window.parent.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
        </script>
        """,
        unsafe_allow_javascript=True,
    )


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
    with open(f"{user_dir}/wellness.pkl", "wb") as f:
        pickle.dump({"mood_entries": [], "mindfulness_log": []}, f)


def verify_password(username, password):
    try:
        with open(f"{USERS_DIR}/{username}/password.txt", "r") as f:
            return f.read() == hash_password(password)
    except Exception:
        return False


def default_wellness_data():
    return {"mood_entries": [], "mindfulness_log": []}


def load_user_data(username):
    user_dir = f"{USERS_DIR}/{username}"
    try:
        with open(f"{user_dir}/profile.pkl", "rb") as f:
            st.session_state.profile = pickle.load(f)
        with open(f"{user_dir}/messages.pkl", "rb") as f:
            st.session_state.messages = pickle.load(f)
    except Exception:
        st.session_state.profile = {}
        st.session_state.messages = []

    try:
        with open(f"{user_dir}/wellness.pkl", "rb") as f:
            st.session_state.wellness = pickle.load(f)
    except Exception:
        st.session_state.wellness = default_wellness_data()

    if not isinstance(st.session_state.wellness, dict):
        st.session_state.wellness = default_wellness_data()
    st.session_state.wellness.setdefault("mood_entries", [])
    st.session_state.wellness.setdefault("mindfulness_log", [])


def save_user_data(username):
    user_dir = f"{USERS_DIR}/{username}"
    with open(f"{user_dir}/profile.pkl", "wb") as f:
        pickle.dump(st.session_state.profile, f)
    with open(f"{user_dir}/messages.pkl", "wb") as f:
        pickle.dump(st.session_state.messages, f)
    with open(f"{user_dir}/wellness.pkl", "wb") as f:
        pickle.dump(st.session_state.get("wellness", default_wellness_data()), f)


def get_response(user_input):
    profile = st.session_state.get("profile", {})
    wellness = st.session_state.get("wellness", default_wellness_data())
    recent_entries = wellness.get("mood_entries", [])[-3:]
    nome = profile.get("nome") or ""
    profile_text = "\n".join([f"- {k}: {v}" for k, v in profile.items() if k != "nome" and v])
    recent_text = "\n".join(
        [
            f"- {entry['data']}: umore {entry['umore']} ({entry['umore_intensita']}/10), "
            f"ansia {entry['ansia']}/10, stress {entry['stress']}/10, trigger: {entry['trigger']}"
            for entry in recent_entries
        ]
    ) or "Nessuna scheda recente."

    system_prompt = f"""Sei PsyHelper, un assistente specializzato in Terapia Cognitivo-Comportamentale.
Nome utente: {nome}
Profilo: {profile_text}
Schede recenti di monitoraggio: {recent_text}
Focalizzati su emozioni, pensieri automatici, trigger, sensazioni corporee e comportamenti. Usa tecniche CBT in modo mirato, concreto e non giudicante.
Non formulare diagnosi e non sostituirti a uno psicologo/psicoterapeuta. In caso di rischio immediato invita a contattare servizi di emergenza o una persona fidata."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

    chain = prompt | llm
    chain_with_history = RunnableWithMessageHistory(chain, lambda x: ChatMessageHistory(), input_messages_key="input", history_messages_key="history")
    response = chain_with_history.invoke({"input": user_input}, config={"configurable": {"session_id": "psyhelper_user"}})
    return response.content


def entries_dataframe():
    entries = st.session_state.get("wellness", default_wellness_data()).get("mood_entries", [])
    if not entries:
        return pd.DataFrame()
    df = pd.DataFrame(entries)
    df["data"] = pd.to_datetime(df["data"])
    return df.sort_values("data")


def most_common_values(series, limit=3):
    values = []
    for item in series.dropna():
        if isinstance(item, list):
            values.extend(item)
        elif item:
            values.extend([part.strip() for part in str(item).split(",") if part.strip()])
    return pd.Series(values).value_counts().head(limit) if values else pd.Series(dtype="int64")


def show_chat_tab():
    st.markdown(f"<p class='subtitle'>Ciao {st.session_state.profile.get('nome', st.session_state.username)}</p>", unsafe_allow_html=True)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Descrivi cosa stai provando o quale esperienza vuoi approfondire..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            with st.spinner("Sto pensando..."):
                reply = get_response(user_input)
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
        save_user_data(st.session_state.username)


def show_diary_tab():
    st.subheader("📝 Scheda stati d'animo, trigger e sensazioni")
    st.caption("Pensata come materiale ordinato da rivedere anche con uno psicologo: emozioni, corpo, pensieri e azioni in un unico schema CBT.")

    with st.form("mood_entry_form"):
        col1, col2 = st.columns(2)
        with col1:
            entry_date = st.date_input("Data", value=date.today())
            mood = st.selectbox("Stato d'animo prevalente", MOOD_OPTIONS)
            mood_intensity = st.slider("Intensità dell'emozione (1-10)", 1, 10, 5)
            anxiety = st.slider("Ansia (0-10)", 0, 10, 4)
            stress = st.slider("Stress (0-10)", 0, 10, 4)
        with col2:
            trigger = st.text_input("Trigger/situazione", placeholder="Es. discussione, scadenza, luogo, pensiero...")
            sensations = st.multiselect("Sensazioni corporee", SENSATION_OPTIONS)
            need = st.text_input("Bisogno emerso", placeholder="Es. sicurezza, riposo, chiarezza, supporto...")
        automatic_thought = st.text_area("Pensiero automatico", placeholder="Che cosa ti sei detto/a in quel momento?")
        behavior = st.text_area("Comportamento o impulso", placeholder="Che cosa hai fatto o avresti voluto fare?")
        balanced_response = st.text_area("Risposta alternativa CBT", placeholder="Quale interpretazione più equilibrata potresti provare?")
        note = st.text_area("Nota per il professionista", placeholder="Elementi che vorresti portare in seduta.")

        if st.form_submit_button("Salva scheda", use_container_width=True):
            entry = {
                "creata_il": datetime.utcnow().isoformat(timespec="seconds"),
                "data": entry_date.isoformat(),
                "umore": mood,
                "umore_intensita": mood_intensity,
                "ansia": anxiety,
                "stress": stress,
                "trigger": trigger,
                "sensazioni": sensations,
                "bisogno": need,
                "pensiero_automatico": automatic_thought,
                "comportamento": behavior,
                "risposta_alternativa": balanced_response,
                "nota_professionista": note,
            }
            st.session_state.wellness["mood_entries"].append(entry)
            save_user_data(st.session_state.username)
            st.success("Scheda salvata. La trovi nel monitoraggio e nel resoconto.")


def show_monitoring_tab():
    st.subheader("📈 Monitoraggio ansia e stress")
    df = entries_dataframe()
    if df.empty:
        st.info("Aggiungi almeno una scheda nel diario per vedere trend e indicatori.")
        return

    latest = df.iloc[-1]
    avg_anxiety = df["ansia"].mean()
    avg_stress = df["stress"].mean()
    col1, col2, col3 = st.columns(3)
    col1.metric("Ultima ansia", f"{latest['ansia']}/10")
    col2.metric("Media ansia", f"{avg_anxiety:.1f}/10")
    col3.metric("Media stress", f"{avg_stress:.1f}/10")

    chart_df = df.melt(id_vars="data", value_vars=["ansia", "stress", "umore_intensita"], var_name="Indicatore", value_name="Valore")
    fig = px.line(chart_df, x="data", y="Valore", color="Indicatore", markers=True, range_y=[0, 10])
    fig.update_layout(xaxis_title="Data", yaxis_title="Intensità", legend_title="Indicatore")
    st.plotly_chart(fig, use_container_width=True)

    trigger_counts = most_common_values(df["trigger"])
    sensation_counts = most_common_values(df["sensazioni"])
    col4, col5 = st.columns(2)
    with col4:
        st.markdown("**Trigger più ricorrenti**")
        st.dataframe(trigger_counts.rename("Frequenza"), use_container_width=True)
    with col5:
        st.markdown("**Sensazioni più ricorrenti**")
        st.dataframe(sensation_counts.rename("Frequenza"), use_container_width=True)


def show_exercises_tab():
    st.subheader("🧘 Esercizi mindfulness su base CBT")
    st.caption("Esercizi brevi per osservare pensieri, emozioni e corpo senza evitare l'esperienza interna.")
    selected = st.selectbox("Scegli un esercizio", list(MINDFULNESS_EXERCISES.keys()))
    exercise = MINDFULNESS_EXERCISES[selected]

    st.markdown(f"**Durata:** {exercise['durata']}")
    st.markdown(f"**Obiettivo CBT:** {exercise['obiettivo']}")
    for index, step in enumerate(exercise["passi"], start=1):
        st.write(f"{index}. {step}")
    st.info(exercise["riflessione"])

    with st.form("mindfulness_log_form"):
        before = st.slider("Ansia/stress prima (0-10)", 0, 10, 5)
        after = st.slider("Ansia/stress dopo (0-10)", 0, 10, 3)
        notes = st.text_area("Cosa hai notato?", placeholder="Pensieri, sensazioni o piccoli cambiamenti osservati.")
        if st.form_submit_button("Registra esercizio", use_container_width=True):
            st.session_state.wellness["mindfulness_log"].append({
                "data": datetime.utcnow().isoformat(timespec="seconds"),
                "esercizio": selected,
                "prima": before,
                "dopo": after,
                "note": notes,
            })
            save_user_data(st.session_state.username)
            st.success("Esercizio registrato.")


def show_report_tab():
    st.subheader("📋 Resoconto per colloqui psicologici")
    df = entries_dataframe()
    if df.empty:
        st.info("Quando avrai salvato alcune schede, qui comparirà un resoconto sintetico esportabile.")
        return

    last_14 = df[df["data"] >= (pd.Timestamp.today().normalize() - pd.Timedelta(days=14))]
    scope_df = last_14 if not last_14.empty else df
    trigger_counts = most_common_values(scope_df["trigger"], limit=5)
    sensation_counts = most_common_values(scope_df["sensazioni"], limit=5)
    mood_counts = scope_df["umore"].value_counts().head(5)

    report = [
        "RESOCONTO PSYHELPER",
        f"Periodo: {scope_df['data'].min().date()} - {scope_df['data'].max().date()}",
        f"Schede compilate: {len(scope_df)}",
        f"Ansia media: {scope_df['ansia'].mean():.1f}/10",
        f"Stress medio: {scope_df['stress'].mean():.1f}/10",
        f"Intensità emotiva media: {scope_df['umore_intensita'].mean():.1f}/10",
        "",
        "Stati d'animo più frequenti:",
        *(f"- {name}: {count}" for name, count in mood_counts.items()),
        "",
        "Trigger ricorrenti:",
        *(f"- {name}: {count}" for name, count in trigger_counts.items()),
        "",
        "Sensazioni corporee ricorrenti:",
        *(f"- {name}: {count}" for name, count in sensation_counts.items()),
        "",
        "Ultime note per il professionista:",
    ]
    notes = scope_df["nota_professionista"].dropna().tail(5)
    report.extend([f"- {note}" for note in notes if str(note).strip()] or ["- Nessuna nota inserita."])
    report_text = "\n".join(report)

    st.text_area("Resoconto sintetico", value=report_text, height=360)
    st.download_button("Scarica resoconto .txt", data=report_text, file_name="resoconto_psyhelper.txt", mime="text/plain", use_container_width=True)

    with st.expander("Vedi schede dettagliate"):
        st.dataframe(scope_df.sort_values("data", ascending=False), use_container_width=True)


# ====================== LOGIN ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Registrati"])
    with tab1:
        with st.form("login"):
            username = st.text_input("Nome utente")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Accedi", use_container_width=True):
                if user_exists(username) and verify_password(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.scroll_to_top = True
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

if st.session_state.pop("scroll_to_top", False):
    scroll_to_top()

st.session_state.setdefault("profile", {})
st.session_state.setdefault("messages", [])
st.session_state.setdefault("wellness", default_wellness_data())
if not isinstance(st.session_state.wellness, dict):
    st.session_state.wellness = default_wellness_data()
st.session_state.wellness.setdefault("mood_entries", [])
st.session_state.wellness.setdefault("mindfulness_log", [])

# ====================== ONBOARDING ======================
if not st.session_state.profile:
    st.markdown("**Benvenuto.** Prima di iniziare, aiutami a conoscerti meglio.")

    with st.form("onboarding"):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Come ti chiami?")
            età = st.number_input("Età", 14, 90, 30)
            umore = st.selectbox("Umore attuale", MOOD_OPTIONS)
            intensità = st.slider("Intensità del malessere (1-10)", 1, 10, 5)
        with col2:
            stress = st.slider("Livello di stress (1-10)", 1, 10, 5)
            sonno = st.selectbox("Sonno ultimamente", ["Buono", "Faccio fatica ad addormentarmi", "Mi sveglio spesso", "Rimugino e non dormo"])
            motivazione = st.slider("Motivazione (1-10)", 1, 10, 7)
        pensieri = st.text_area("Quali pensieri ti occupano di più ultimamente?")
        obiettivi = st.text_area("Cosa vorresti migliorare nel tuo benessere mentale?")
        if st.form_submit_button("Inizia il percorso 💜", use_container_width=True):
            st.session_state.profile = {
                "nome": nome or "Utente",
                "età": età,
                "umore": umore,
                "intensità": intensità,
                "stress": stress,
                "sonno": sonno,
                "pensieri": pensieri,
                "obiettivi": obiettivi,
                "motivazione": motivazione,
            }
            st.session_state.scroll_to_top = True
            save_user_data(st.session_state.username)
            st.rerun()
    st.stop()

# ====================== AREA APP ======================
app_tabs = st.tabs(["💬 Chat", "📝 Diario CBT", "📈 Monitoraggio", "🧘 Esercizi", "📋 Resoconto"])
with app_tabs[0]:
    show_chat_tab()
with app_tabs[1]:
    show_diary_tab()
with app_tabs[2]:
    show_monitoring_tab()
with app_tabs[3]:
    show_exercises_tab()
with app_tabs[4]:
    show_report_tab()

st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Nuova sessione"):
        st.session_state.messages = []
        save_user_data(st.session_state.username)
        st.session_state.scroll_to_top = True
        st.rerun()
with col2:
    if st.button("Torna in alto"):
        scroll_to_top()
with col3:
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.scroll_to_top = True
        st.rerun()
