import hashlib
import os
import pickle
import re
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_groq import ChatGroq

st.set_page_config(page_title="PsyHelper", page_icon="🧠", layout="centered")

ANALYTICS_ID = "G-KWR24JLV0Y"
COPYRIGHT_POLICY = """
Policy copyright: non riprodurre o continuare testi protetti da copyright non forniti dall'utente, inclusi brani di libri, articoli, canzoni, manuali o materiali formativi.
Se l'utente chiede contenuti protetti estesi, rifiuta brevemente la riproduzione e offri invece riassunti, spiegazioni, parafrasi brevi, analisi o indicazioni originali.
Se l'utente fornisce personalmente un breve estratto, puoi commentarlo o trasformarlo limitando le citazioni testuali allo stretto necessario.
"""


def render_analytics_banner():
    st.sidebar.markdown("### Privacy e analytics")
    st.sidebar.caption(
        "Google Analytics resta disattivato finché non dai consenso. "
        "Se attivato, vengono raccolte metriche d'uso aggregate; non inserire dati sensibili nei campi liberi se non necessario."
    )
    consent = st.sidebar.checkbox(
        "Acconsento all'uso di Google Analytics",
        value=st.session_state.get("analytics_consent", False),
        key="analytics_consent_checkbox",
    )
    st.session_state.analytics_consent = consent

    if not consent:
        st.sidebar.info("Analytics disattivato: nessuno script Google Analytics viene caricato.")
        return

    st.sidebar.success("Analytics attivato per questa sessione.")
    st.markdown(
        f"""
<script async src="https://www.googletagmanager.com/gtag/js?id={ANALYTICS_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ANALYTICS_ID}', {{ 'anonymize_ip': true }});
</script>
""",
        unsafe_allow_html=True,
    )


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

render_analytics_banner()

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


def normalize_username(username):
    normalized = username.strip().lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_-]", "", normalized)


def user_dir(username):
    return os.path.join(USERS_DIR, normalize_username(username))


def user_exists(username):
    return os.path.isdir(user_dir(username))


def default_user_metadata(role="client", therapist_username=None, subscription_status="inactive"):
    return {
        "role": role,
        "therapist_username": normalize_username(therapist_username) if therapist_username else None,
        "subscription_status": subscription_status,
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


def load_user_metadata(username):
    if not user_exists(username):
        return default_user_metadata(role="therapist", subscription_status="inactive")

    metadata_path = os.path.join(user_dir(username), "metadata.pkl")
    try:
        with open(metadata_path, "rb") as f:
            metadata = pickle.load(f)
    except Exception:
        # Compatibilità con account creati prima del modello psicologo/cliente:
        # li trattiamo come professionisti attivi per non bloccare gli utenti esistenti.
        metadata = default_user_metadata(role="therapist", subscription_status="active")

    metadata.setdefault("role", "client")
    metadata.setdefault("therapist_username", None)
    metadata.setdefault("subscription_status", "inactive")
    metadata.setdefault("created_at", datetime.utcnow().isoformat(timespec="seconds"))
    return metadata


def save_user_metadata(username, metadata):
    os.makedirs(user_dir(username), exist_ok=True)
    with open(os.path.join(user_dir(username), "metadata.pkl"), "wb") as f:
        pickle.dump(metadata, f)


def create_user(username, password, role="client", therapist_username=None, subscription_status="inactive", profile=None):
    username = normalize_username(username)
    account_dir = user_dir(username)
    os.makedirs(account_dir, exist_ok=True)
    with open(os.path.join(account_dir, "password.txt"), "w") as f:
        f.write(hash_password(password))
    with open(os.path.join(account_dir, "profile.pkl"), "wb") as f:
        pickle.dump(profile or {}, f)
    with open(os.path.join(account_dir, "messages.pkl"), "wb") as f:
        pickle.dump([], f)
    with open(os.path.join(account_dir, "wellness.pkl"), "wb") as f:
        pickle.dump(default_wellness_data(), f)
    save_user_metadata(
        username,
        default_user_metadata(
            role=role,
            therapist_username=therapist_username,
            subscription_status=subscription_status,
        ),
    )


def create_client_account(therapist_username, client_username, password, display_name):
    create_user(
        client_username,
        password,
        role="client",
        therapist_username=therapist_username,
        subscription_status="covered_by_therapist",
        profile={"nome": display_name or normalize_username(client_username), "onboarding_completed": False},
    )


def verify_password(username, password):
    try:
        with open(os.path.join(user_dir(username), "password.txt"), "r") as f:
            return f.read() == hash_password(password)
    except Exception:
        return False


def default_wellness_data():
    return {"mood_entries": [], "mindfulness_log": []}


def load_user_data(username):
    account_dir = user_dir(username)
    st.session_state.user_metadata = load_user_metadata(username)
    try:
        with open(os.path.join(account_dir, "profile.pkl"), "rb") as f:
            st.session_state.profile = pickle.load(f)
        with open(os.path.join(account_dir, "messages.pkl"), "rb") as f:
            st.session_state.messages = pickle.load(f)
    except Exception:
        st.session_state.profile = {}
        st.session_state.messages = []

    try:
        with open(os.path.join(account_dir, "wellness.pkl"), "rb") as f:
            st.session_state.wellness = pickle.load(f)
    except Exception:
        st.session_state.wellness = default_wellness_data()

    if not isinstance(st.session_state.wellness, dict):
        st.session_state.wellness = default_wellness_data()
    st.session_state.wellness.setdefault("mood_entries", [])
    st.session_state.wellness.setdefault("mindfulness_log", [])


def save_user_data(username):
    account_dir = user_dir(username)
    with open(os.path.join(account_dir, "profile.pkl"), "wb") as f:
        pickle.dump(st.session_state.profile, f)
    with open(os.path.join(account_dir, "messages.pkl"), "wb") as f:
        pickle.dump(st.session_state.messages, f)
    with open(os.path.join(account_dir, "wellness.pkl"), "wb") as f:
        pickle.dump(st.session_state.get("wellness", default_wellness_data()), f)


def active_subscription_statuses():
    configured_statuses = st.secrets.get("ACTIVE_SUBSCRIPTION_STATUSES", "active,trialing")
    return {status.strip().lower() for status in configured_statuses.split(",") if status.strip()}


def is_subscription_active_for(username):
    metadata = load_user_metadata(username)
    if metadata.get("role") == "client":
        therapist_username = metadata.get("therapist_username")
        return bool(therapist_username and is_subscription_active_for(therapist_username))
    return metadata.get("subscription_status", "inactive").lower() in active_subscription_statuses()


def client_accounts_for(therapist_username):
    clients = []
    therapist_username = normalize_username(therapist_username)
    for account_name in sorted(os.listdir(USERS_DIR)):
        if not user_exists(account_name):
            continue
        metadata = load_user_metadata(account_name)
        if metadata.get("role") == "client" and metadata.get("therapist_username") == therapist_username:
            profile_path = os.path.join(user_dir(account_name), "profile.pkl")
            try:
                with open(profile_path, "rb") as f:
                    profile = pickle.load(f)
            except Exception:
                profile = {}
            clients.append({
                "username": account_name,
                "nome": profile.get("nome", account_name),
                "creato_il": metadata.get("created_at", ""),
            })
    return clients


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
Non formulare diagnosi e non sostituirti a uno psicologo/psicoterapeuta. In caso di rischio immediato invita a contattare servizi di emergenza o una persona fidata.
{COPYRIGHT_POLICY}"""

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


def show_subscription_required(account_label, therapist_username=None):
    st.warning(
        "Per usare PsyHelper serve un abbonamento professionale attivo. "
        "Gli account cliente sono coperti dall'abbonamento dello psicologo che li ha creati."
    )
    if therapist_username:
        st.info(f"Questo account cliente è collegato allo psicologo: `{therapist_username}`.")

    checkout_url = st.secrets.get("SUBSCRIPTION_CHECKOUT_URL", "")
    if checkout_url:
        st.link_button("Attiva o rinnova abbonamento", checkout_url, use_container_width=True)
    else:
        st.caption(
            "In produzione collega qui Stripe Checkout/Customer Portal impostando "
            "`SUBSCRIPTION_CHECKOUT_URL` nei secrets e aggiornando `subscription_status` via webhook."
        )
    st.caption(f"Account: {account_label}")


def show_therapist_dashboard():
    username = st.session_state.username
    metadata = st.session_state.get("user_metadata", load_user_metadata(username))
    subscription_status = metadata.get("subscription_status", "inactive")
    subscription_active = is_subscription_active_for(username)

    st.header("👩‍⚕️ Dashboard professionista")
    st.write(
        "Con questo modello lo psicologo paga un solo abbonamento mensile e può creare "
        "account cliente separati. Ogni cliente accede con credenziali proprie e i suoi dati "
        "restano nel suo spazio dedicato."
    )

    col1, col2 = st.columns(2)
    col1.metric("Abbonamento", "Attivo" if subscription_active else "Non attivo")
    col2.metric("Stato", subscription_status)

    if not subscription_active:
        show_subscription_required(username)
        return

    st.subheader("Crea account cliente")
    with st.form("create_client_account"):
        client_name = st.text_input("Nome cliente", placeholder="Es. Cliente Rossi")
        client_username = st.text_input("Username cliente", placeholder="cliente_rossi")
        client_password = st.text_input("Password temporanea", type="password")
        confirm_client_password = st.text_input("Conferma password temporanea", type="password")
        if st.form_submit_button("Crea cliente", use_container_width=True):
            normalized_client_username = normalize_username(client_username)
            if not client_name.strip():
                st.error("Inserisci il nome del cliente.")
            elif len(normalized_client_username) < 3:
                st.error("Lo username cliente deve avere almeno 3 caratteri.")
            elif user_exists(normalized_client_username):
                st.error("Username cliente già esistente.")
            elif len(client_password) < 8:
                st.error("La password temporanea deve avere almeno 8 caratteri.")
            elif client_password != confirm_client_password:
                st.error("Le password non coincidono.")
            else:
                create_client_account(username, normalized_client_username, client_password, client_name.strip())
                st.success(
                    f"Account cliente `{normalized_client_username}` creato. "
                    "Consegna le credenziali al cliente e chiedigli di cambiarle appena disponibile la funzione cambio password."
                )

    st.subheader("Clienti collegati")
    clients = client_accounts_for(username)
    if clients:
        st.dataframe(pd.DataFrame(clients), use_container_width=True, hide_index=True)
    else:
        st.info("Non hai ancora creato account cliente.")


def logout_button():
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_metadata = {}
        st.session_state.profile = {}
        st.session_state.messages = []
        st.session_state.wellness = default_wellness_data()
        st.session_state.scroll_to_top = True
        st.rerun()


# ====================== LOGIN ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Registrati come psicologo"])
    with tab1:
        st.caption("I clienti non si registrano da soli: ricevono l'account dal proprio psicologo abbonato.")
        with st.form("login"):
            username = st.text_input("Nome utente")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Accedi", use_container_width=True):
                normalized_username = normalize_username(username)
                if user_exists(normalized_username) and verify_password(normalized_username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = normalized_username
                    st.session_state.scroll_to_top = True
                    load_user_data(normalized_username)
                    st.rerun()
                else:
                    st.error("Nome utente o password errati")
    with tab2:
        st.info(
            "Crea l'account professionista. L'abbonamento mensile è collegato a questo account; "
            "da qui potrai creare tutti gli account cliente necessari."
        )
        with st.form("therapist_signup"):
            professional_name = st.text_input("Nome professionista o studio")
            new_username = st.text_input("Scegli un nome utente professionista")
            new_password = st.text_input("Scegli una password", type="password")
            confirm_password = st.text_input("Conferma password", type="password")
            if st.form_submit_button("Crea account professionista", use_container_width=True):
                normalized_username = normalize_username(new_username)
                initial_status = st.secrets.get("NEW_THERAPIST_SUBSCRIPTION_STATUS", "trialing")
                if not professional_name.strip():
                    st.error("Inserisci il nome del professionista o dello studio.")
                elif new_password != confirm_password:
                    st.error("Le password non coincidono")
                elif user_exists(normalized_username):
                    st.error("Nome utente già esistente")
                elif len(normalized_username) < 3:
                    st.error("Il nome utente deve avere almeno 3 caratteri")
                elif len(new_password) < 8:
                    st.error("La password deve avere almeno 8 caratteri")
                else:
                    create_user(
                        normalized_username,
                        new_password,
                        role="therapist",
                        subscription_status=initial_status,
                        profile={"nome": professional_name.strip(), "account_type": "therapist"},
                    )
                    st.success(
                        "Account professionista creato. Ora effettua il login; "
                        "in produzione lo stato abbonamento sarà aggiornato dal sistema pagamenti."
                    )
    st.stop()

if st.session_state.pop("scroll_to_top", False):
    scroll_to_top()

st.session_state.setdefault("profile", {})
st.session_state.setdefault("messages", [])
st.session_state.setdefault("wellness", default_wellness_data())
st.session_state.setdefault("user_metadata", load_user_metadata(st.session_state.username))
if not isinstance(st.session_state.wellness, dict):
    st.session_state.wellness = default_wellness_data()
st.session_state.wellness.setdefault("mood_entries", [])
st.session_state.wellness.setdefault("mindfulness_log", [])

current_metadata = st.session_state.get("user_metadata", {})
current_role = current_metadata.get("role", "client")

if current_role == "therapist":
    show_therapist_dashboard()
    st.divider()
    logout_button()
    st.stop()

if not is_subscription_active_for(st.session_state.username):
    show_subscription_required(st.session_state.username, current_metadata.get("therapist_username"))
    st.divider()
    logout_button()
    st.stop()

# ====================== ONBOARDING ======================
if not st.session_state.profile.get("onboarding_completed", False):
    st.markdown("**Benvenuto.** Prima di iniziare, aiutami a conoscerti meglio.")

    with st.form("onboarding"):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Come ti chiami?", value=st.session_state.profile.get("nome", ""))
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
                "onboarding_completed": True,
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
        st.session_state.user_metadata = {}
        st.session_state.profile = {}
        st.session_state.messages = []
        st.session_state.wellness = default_wellness_data()
        st.session_state.scroll_to_top = True
        st.rerun()
