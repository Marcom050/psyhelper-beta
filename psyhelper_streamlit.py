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

st.set_page_config(page_title="PsyHelper", page_icon="🧠", layout="wide")

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
CBT_HOMEWORK_TEMPLATES = {
    "ABC model": {
        "obiettivo": "Collegare situazione, pensieri/convinzioni e conseguenze emotive/comportamentali.",
        "campi": ["A - Evento attivante", "B - Pensieri/convinzioni", "C - Emozioni e comportamenti", "Ipotesi alternativa", "Prossimo passo"]
    },
    "Thought record": {
        "obiettivo": "Raccogliere prove a favore/contro un pensiero automatico e formulare una risposta bilanciata.",
        "campi": ["Situazione", "Emozione 0-10", "Pensiero automatico", "Prove a favore", "Prove contro", "Pensiero alternativo", "Emozione dopo 0-10"]
    },
    "Ristrutturazione cognitiva": {
        "obiettivo": "Individuare distorsioni cognitive e costruire una valutazione più utile e realistica.",
        "campi": ["Pensiero target", "Distorsione possibile", "Domanda socratica", "Risposta più equilibrata", "Azione coerente"]
    },
    "Esposizione graduale": {
        "obiettivo": "Pianificare piccoli passi di esposizione monitorando ansia prevista, ansia reale ed evitamento.",
        "campi": ["Situazione temuta", "Step di esposizione", "Ansia prevista 0-10", "Ansia massima reale 0-10", "Cosa ho imparato", "Evitamenti/safety behavior"]
    },
    "Monitoraggio evitamento": {
        "obiettivo": "Rendere visibili situazioni evitate, costo dell'evitamento e alternative praticabili.",
        "campi": ["Situazione evitata", "Emozione associata", "Cosa ho evitato", "Costo a breve/lungo termine", "Micro-azione alternativa"]
    },
    "Behavioral activation": {
        "obiettivo": "Programmare attività coerenti con valori, piacere o padronanza e monitorarne l'effetto.",
        "campi": ["Attività programmata", "Valore collegato", "Difficoltà prevista 0-10", "Piacere/padronanza dopo 0-10", "Ostacoli", "Prossimo passo"]
    },
    "Scheda emozioni": {
        "obiettivo": "Descrivere emozioni, intensità, bisogni e strategie di regolazione utili.",
        "campi": ["Emozione", "Intensità 0-10", "Segnali corporei", "Bisogno", "Strategia utile", "Esito"]
    },
    "Scheda trigger": {
        "obiettivo": "Mappare trigger ricorrenti, contesto e risposta comportamentale.",
        "campi": ["Trigger", "Contesto", "Pensieri emersi", "Emozioni", "Comportamento", "Risposta alternativa"]
    },
}

HIGH_RISK_KEYWORDS = [
    "suicidio", "suicid", "farla finita", "non voglio vivere", "uccidermi", "autolesion", "tagliarmi",
    "morire", "overdose", "impicc", "buttarmi", "sparire per sempre",
]

AVOIDANCE_KEYWORDS = ["evito", "evitare", "rimando", "non sono uscito", "annullo", "isolamento", "mi isolo", "scappo"]
CATASTROPHIC_KEYWORDS = ["disastro", "catastrofe", "terribile", "non ce la farò", "andrà malissimo", "rovinerò", "fallirò"]
SOCIAL_KEYWORDS = ["sociale", "persone", "uscire", "gruppo", "festa", "colleghi", "giudicano", "vergogna"]
WORK_KEYWORDS = ["lavoro", "capo", "collega", "scadenza", "ufficio", "riunione", "cliente", "turno"]

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
    return {
        "mood_entries": [],
        "homework_assignments": [],
        "homework_submissions": [],
        "timeline_events": [],
    }


def ensure_wellness_schema(wellness):
    wellness.setdefault("mood_entries", [])
    wellness.setdefault("homework_assignments", [])
    wellness.setdefault("homework_submissions", [])
    wellness.setdefault("timeline_events", [])
    # Migrazione: la vecchia app salvava log mindfulness; non viene più mostrato nel prodotto clinico.
    wellness.pop("mindfulness_log", None)
    return wellness


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
    ensure_wellness_schema(st.session_state.wellness)


def save_user_data(username):
    account_dir = user_dir(username)
    with open(os.path.join(account_dir, "profile.pkl"), "wb") as f:
        pickle.dump(st.session_state.profile, f)
    with open(os.path.join(account_dir, "messages.pkl"), "wb") as f:
        pickle.dump(st.session_state.messages, f)
    with open(os.path.join(account_dir, "wellness.pkl"), "wb") as f:
        pickle.dump(ensure_wellness_schema(st.session_state.get("wellness", default_wellness_data())), f)


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


def load_account_bundle(username):
    account_dir = user_dir(username)
    try:
        with open(os.path.join(account_dir, "profile.pkl"), "rb") as f:
            profile = pickle.load(f)
    except Exception:
        profile = {}
    try:
        with open(os.path.join(account_dir, "messages.pkl"), "rb") as f:
            messages = pickle.load(f)
    except Exception:
        messages = []
    try:
        with open(os.path.join(account_dir, "wellness.pkl"), "rb") as f:
            wellness = pickle.load(f)
    except Exception:
        wellness = default_wellness_data()
    if not isinstance(wellness, dict):
        wellness = default_wellness_data()
    return {"profile": profile, "messages": messages, "wellness": ensure_wellness_schema(wellness)}


def save_wellness_for(username, wellness):
    account_dir = user_dir(username)
    os.makedirs(account_dir, exist_ok=True)
    with open(os.path.join(account_dir, "wellness.pkl"), "wb") as f:
        pickle.dump(ensure_wellness_schema(wellness), f)


def therapist_notes_path(therapist_username):
    return os.path.join(user_dir(therapist_username), "therapist_notes.pkl")


def load_therapist_notes(therapist_username):
    try:
        with open(therapist_notes_path(therapist_username), "rb") as f:
            notes = pickle.load(f)
    except Exception:
        notes = {}
    return notes if isinstance(notes, dict) else {}


def save_therapist_notes(therapist_username, notes):
    with open(therapist_notes_path(therapist_username), "wb") as f:
        pickle.dump(notes, f)


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


def clean_text(value):
    return str(value or "").strip()


def homework_questions_for(template_name, assignment=None):
    assignment = assignment or {}
    custom_questions = [clean_text(question) for question in assignment.get("questions", [])]
    custom_questions = [question for question in custom_questions if question]
    if custom_questions:
        return custom_questions

    guided_questions = {
        "ABC model": ["Che cosa è successo?", "Che cosa ti è passato per la mente?", "Che effetto ha avuto su emozioni o comportamento?"],
        "Thought record": ["Quale pensiero automatico hai notato?", "Quali elementi lo confermano o lo mettono in dubbio?", "Quale risposta più equilibrata puoi provare?"],
        "Ristrutturazione cognitiva": ["Quale pensiero vuoi rivedere?", "Quale modo alternativo di leggerlo può essere più utile?", "Quale piccola azione coerente puoi fare?"],
        "Esposizione graduale": ["Quale passo di esposizione hai provato?", "Com'è andata durante e dopo?", "Che cosa hai imparato?"],
        "Monitoraggio evitamento": ["Quale situazione hai evitato o avresti voluto evitare?", "Che costo ha avuto l'evitamento?", "Quale micro-azione alternativa puoi provare?"],
        "Behavioral activation": ["Quale attività hai programmato o svolto?", "Che effetto ha avuto su umore, energia o senso di efficacia?", "Qual è il prossimo piccolo passo?"],
        "Scheda emozioni": ["Quale emozione hai notato?", "Quale bisogno segnalava?", "Che cosa ti ha aiutato o potrebbe aiutarti?"],
        "Scheda trigger": ["Quale trigger hai notato?", "In quale contesto è comparso?", "Quale risposta alternativa puoi provare?"],
    }
    return guided_questions.get(template_name, ["Scrivi qui la tua risposta"])


def homework_answer_items(answers):
    if isinstance(answers, dict):
        return [(clean_text(question), clean_text(answer)) for question, answer in answers.items() if clean_text(answer)]
    if isinstance(answers, list):
        return [(f"Risposta {index}", clean_text(answer)) for index, answer in enumerate(answers, start=1) if clean_text(answer)]
    answer = clean_text(answers)
    return [("Risposta", answer)] if answer else []


def homework_readable_summary(submission):
    summary = clean_text(submission.get("summary"))
    answer_items = homework_answer_items(submission.get("answers", {}))
    if summary:
        return summary
    if answer_items:
        return " · ".join(answer for _, answer in answer_items[:2])
    return "Nessuna risposta inserita."


def render_homework_answers(submission):
    answer_items = homework_answer_items(submission.get("answers", {}))
    if not answer_items:
        st.info("Nessuna risposta inserita.")
        return
    for question, answer in answer_items:
        st.markdown(f"**{question}**")
        st.write(answer)


def homework_assignment_rows(assignments, completed_ids):
    rows = []
    for assignment in assignments:
        rows.append({
            "homework": assignment.get("template", "Homework"),
            "scadenza": assignment.get("due_date", "—"),
            "stato": "Completato" if assignment.get("id") in completed_ids or assignment.get("status") == "completato" else "Da completare",
            "istruzioni": clean_text(assignment.get("instructions")) or "—",
        })
    return rows


def text_blob_from_entries(entries):
    fields = ["trigger", "pensiero_automatico", "comportamento", "risposta_alternativa", "nota_professionista", "bisogno"]
    return " ".join(str(entry.get(field, "")) for entry in entries for field in fields).lower()


def keyword_hits(text, keywords):
    return sum(1 for keyword in keywords if keyword in text)


def clinical_snapshot(wellness, messages=None):
    entries = ensure_wellness_schema(wellness).get("mood_entries", [])
    messages = messages or []
    assignments = wellness.get("homework_assignments", [])
    submissions = wellness.get("homework_submissions", [])
    if entries:
        df = pd.DataFrame(entries)
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.dropna(subset=["data"]).sort_values("data")
    else:
        df = pd.DataFrame()

    now = pd.Timestamp.today().normalize()
    last_14 = df[df["data"] >= now - pd.Timedelta(days=14)] if not df.empty else pd.DataFrame()
    prev_14 = df[(df["data"] < now - pd.Timedelta(days=14)) & (df["data"] >= now - pd.Timedelta(days=28))] if not df.empty else pd.DataFrame()
    scope_df = last_14 if not last_14.empty else df

    insights = []
    alerts = []
    if not scope_df.empty:
        avg_anxiety = scope_df["ansia"].mean()
        avg_stress = scope_df["stress"].mean()
        latest = scope_df.iloc[-1]
        if latest.get("ansia", 0) >= 8 or latest.get("umore_intensita", 0) >= 8:
            alerts.append("Forte intensità emotiva recente: potenziale area da attenzionare.")
        if not prev_14.empty and avg_anxiety - prev_14["ansia"].mean() >= 1.5:
            insights.append("Ansia in aumento rispetto alle 2 settimane precedenti.")
        monday_df = df[df["data"].dt.weekday == 0]
        if len(monday_df) >= 2 and monday_df["ansia"].mean() >= df["ansia"].mean() + 1:
            insights.append("Ansia tendenzialmente più alta il lunedì.")
        trigger_counts = most_common_values(scope_df.get("trigger", pd.Series(dtype="object")), limit=3)
        for trigger, count in trigger_counts.items():
            if count >= 2:
                insights.append(f"Trigger ricorrente: {trigger} ({count} rilevazioni).")
        if len(scope_df) <= 1 and len(df) >= 3:
            alerts.append("Riduzione delle compilazioni recenti: possibile rischio drop-out o calo aderenza.")
        last_entry_date = df["data"].max() if not df.empty else None
        if last_entry_date is not None and (now - last_entry_date.normalize()).days >= 7:
            alerts.append("Nessuna compilazione negli ultimi 7 giorni: verificare engagement.")
    else:
        avg_anxiety = avg_stress = 0
        alerts.append("Nessuna scheda compilata: aderenza non valutabile.")

    text_blob = text_blob_from_entries(entries) + " " + " ".join(str(m.get("content", "")) for m in messages).lower()
    if keyword_hits(text_blob, HIGH_RISK_KEYWORDS):
        alerts.append("Parole ad alto rischio rilevate: potenziale area da attenzionare, senza diagnosi automatica.")
    if keyword_hits(text_blob, CATASTROPHIC_KEYWORDS) >= 2:
        insights.append("Pensieri catastrofici ricorrenti nel materiale scritto.")
    if keyword_hits(text_blob, AVOIDANCE_KEYWORDS) >= 2:
        insights.append("Indicatori di evitamento in aumento o ricorrenti.")
    if keyword_hits(text_blob, SOCIAL_KEYWORDS) >= 2:
        insights.append("Temi sociali/interpersonali ricorrenti.")
    if keyword_hits(text_blob, WORK_KEYWORDS) >= 2:
        insights.append("Trigger legati al lavoro ricorrenti.")

    completed_ids = {submission.get("assignment_id") for submission in submissions}
    total_assignments = len(assignments)
    completed_assignments = len([a for a in assignments if a.get("id") in completed_ids or a.get("status") == "completato"])
    overdue = []
    for assignment in assignments:
        due_date = assignment.get("due_date")
        if assignment.get("id") in completed_ids:
            continue
        if due_date and pd.to_datetime(due_date, errors="coerce") < now:
            overdue.append(assignment)
    if overdue:
        alerts.append(f"{len(overdue)} homework assegnati risultano oltre scadenza.")

    return {
        "entries_count": len(scope_df),
        "avg_anxiety": avg_anxiety,
        "avg_stress": avg_stress,
        "insights": insights[:6] or ["Servono più dati recenti per generare pattern affidabili."],
        "alerts": alerts[:6],
        "homework_total": total_assignments,
        "homework_completed": completed_assignments,
        "homework_compliance": (completed_assignments / total_assignments * 100) if total_assignments else 0,
        "last_activity": df["data"].max().date().isoformat() if not df.empty else "—",
        "scope_df": scope_df,
    }


def weekly_recap(snapshot):
    return [
        f"Schede ultime 2 settimane: {snapshot['entries_count']}",
        f"Ansia media: {snapshot['avg_anxiety']:.1f}/10",
        f"Stress medio: {snapshot['avg_stress']:.1f}/10",
        f"Homework completati: {snapshot['homework_completed']} su {snapshot['homework_total']} ({snapshot['homework_compliance']:.0f}%)",
        *snapshot["insights"][:4],
    ]


def build_timeline_events(wellness):
    events = []
    for entry in wellness.get("mood_entries", []):
        events.append({
            "data": entry.get("data", entry.get("creata_il", "")),
            "tipo": "Diario",
            "titolo": f"{entry.get('umore', 'Umore')} · ansia {entry.get('ansia', '—')}/10",
            "dettaglio": entry.get("trigger") or entry.get("pensiero_automatico") or "Scheda CBT compilata",
        })
    for assignment in wellness.get("homework_assignments", []):
        events.append({
            "data": assignment.get("assigned_at", ""),
            "tipo": "Homework assegnato",
            "titolo": assignment.get("template", "Homework"),
            "dettaglio": assignment.get("instructions", ""),
        })
    for submission in wellness.get("homework_submissions", []):
        events.append({
            "data": submission.get("submitted_at", ""),
            "tipo": "Homework completato",
            "titolo": submission.get("template", "Homework"),
            "dettaglio": submission.get("summary", ""),
        })
    events.extend(wellness.get("timeline_events", []))
    return sorted(events, key=lambda item: str(item.get("data", "")), reverse=True)


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

    snapshot = clinical_snapshot(st.session_state.wellness, st.session_state.messages)
    latest = df.iloc[-1]
    avg_anxiety = df["ansia"].mean()
    avg_stress = df["stress"].mean()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ultima ansia", f"{latest['ansia']}/10")
    col2.metric("Media ansia", f"{avg_anxiety:.1f}/10")
    col3.metric("Media stress", f"{avg_stress:.1f}/10")
    col4.metric("Homework", f"{snapshot['homework_completed']}/{snapshot['homework_total']}")

    with st.expander("Insight automatici da portare in seduta", expanded=True):
        for insight in snapshot["insights"]:
            st.write(f"• {insight}")
        for alert in snapshot["alerts"]:
            st.warning(f"Potenziale area da attenzionare: {alert}")

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


def show_homework_tab():
    st.subheader("📚 Homework")
    ensure_wellness_schema(st.session_state.wellness)

    assignments = st.session_state.wellness["homework_assignments"]
    submissions = st.session_state.wellness["homework_submissions"]
    completed_ids = {submission.get("assignment_id") for submission in submissions}
    open_assignments = [assignment for assignment in assignments if assignment.get("id") not in completed_ids]

    if open_assignments:
        st.markdown("### Compiti assegnati dal terapeuta")
        selected_assignment = st.selectbox(
            "Seleziona il compito da completare",
            open_assignments,
            format_func=lambda item: f"{item.get('template', 'Homework')} · scadenza {item.get('due_date', 'non indicata')}",
        )
        template_name = selected_assignment.get("template")
        questions = homework_questions_for(template_name, selected_assignment)
        st.caption(f"Scadenza: {selected_assignment.get('due_date', 'non indicata')}")
        if clean_text(selected_assignment.get("instructions")):
            st.info(selected_assignment.get("instructions"))
        with st.form("assigned_homework_submission"):
            answers = {}
            for index, question in enumerate(questions, start=1):
                answers[question] = st.text_area(
                    question,
                    key=f"assigned_{selected_assignment.get('id')}_{index}",
                    height=140 if len(questions) == 1 else 100,
                    placeholder="Rispondi qui.",
                )
            summary = st.text_area(
                "Nota facoltativa",
                placeholder="Aggiungi qualcosa da discutere in seduta, se serve.",
                height=90,
            )
            if st.form_submit_button("Invia al terapeuta", use_container_width=True):
                submissions.append({
                    "assignment_id": selected_assignment.get("id"),
                    "template": template_name,
                    "submitted_at": datetime.utcnow().isoformat(timespec="seconds"),
                    "answers": answers,
                    "summary": summary,
                })
                save_user_data(st.session_state.username)
                st.success("Homework inviato.")
                st.rerun()
    else:
        st.info("Non ci sono homework assegnati aperti. Se vuoi puoi salvare una nota libera da portare in seduta.")

    st.markdown("### Homework libero")
    selected = st.selectbox("Scegli homework CBT", list(CBT_HOMEWORK_TEMPLATES.keys()))
    with st.form("free_homework_submission"):
        answers = {}
        for index, question in enumerate(homework_questions_for(selected), start=1):
            answers[question] = st.text_area(
                question,
                key=f"free_{selected}_{index}",
                height=140 if len(homework_questions_for(selected)) == 1 else 100,
                placeholder="Rispondi qui.",
            )
        summary = st.text_area("Nota facoltativa", placeholder="Aggiungi qualcosa da discutere in seduta, se serve.", height=90)
        if st.form_submit_button("Salva nota", use_container_width=True):
            submissions.append({
                "assignment_id": None,
                "template": selected,
                "submitted_at": datetime.utcnow().isoformat(timespec="seconds"),
                "answers": answers,
                "summary": summary,
            })
            save_user_data(st.session_state.username)
            st.success("Homework salvato.")

    if submissions:
        with st.expander("Storico homework e note"):
            rows = [
                {
                    "data": item.get("submitted_at"),
                    "homework": item.get("template"),
                    "risposte": homework_readable_summary(item),
                }
                for item in submissions
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


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

    st.header("👩‍⚕️ Dashboard terapeuta intelligente")
    st.caption("Focus clinico: overview pazienti, insight automatici, aderenza, alert e organizzazione del materiale per la seduta.")

    col1, col2 = st.columns(2)
    col1.metric("Abbonamento", "Attivo" if subscription_active else "Non attivo")
    col2.metric("Stato", subscription_status)

    if not subscription_active:
        show_subscription_required(username)
        return

    with st.expander("➕ Crea account cliente", expanded=False):
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
                    st.success(f"Account cliente `{normalized_client_username}` creato.")

    clients = client_accounts_for(username)
    if not clients:
        st.info("Non hai ancora creato account cliente.")
        return

    overview_rows = []
    bundles = {}
    for client in clients:
        bundle = load_account_bundle(client["username"])
        bundles[client["username"]] = bundle
        snapshot = clinical_snapshot(bundle["wellness"], bundle["messages"])
        overview_rows.append({
            "cliente": client["nome"],
            "username": client["username"],
            "ultima attività": snapshot["last_activity"],
            "ansia media 14g": f"{snapshot['avg_anxiety']:.1f}/10",
            "stress medio 14g": f"{snapshot['avg_stress']:.1f}/10",
            "homework": f"{snapshot['homework_completed']}/{snapshot['homework_total']}",
            "alert": len(snapshot["alerts"]),
            "insight principale": snapshot["insights"][0],
        })

    st.subheader("Overview pazienti")
    st.dataframe(pd.DataFrame(overview_rows), use_container_width=True, hide_index=True)

    selected_username = st.selectbox(
        "Apri scheda paziente",
        [client["username"] for client in clients],
        format_func=lambda item: next((client["nome"] for client in clients if client["username"] == item), item),
    )
    selected_bundle = bundles[selected_username]
    selected_profile = selected_bundle["profile"]
    selected_wellness = selected_bundle["wellness"]
    selected_snapshot = clinical_snapshot(selected_wellness, selected_bundle["messages"])

    st.markdown(f"## {selected_profile.get('nome', selected_username)}")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Ansia media", f"{selected_snapshot['avg_anxiety']:.1f}/10")
    kpi2.metric("Stress medio", f"{selected_snapshot['avg_stress']:.1f}/10")
    kpi3.metric("Aderenza homework", f"{selected_snapshot['homework_compliance']:.0f}%")
    kpi4.metric("Alert aperti", len(selected_snapshot["alerts"]))

    detail_tabs = st.tabs(["🧠 Insight", "📊 Trend", "📚 Homework", "🗓️ Timeline", "🔒 Note private", "📄 Recap seduta"])
    with detail_tabs[0]:
        st.markdown("### Insight automatici clinicamente utili")
        for insight in selected_snapshot["insights"]:
            st.success(f"• {insight}")
        st.markdown("### Alert intelligenti")
        if selected_snapshot["alerts"]:
            for alert in selected_snapshot["alerts"]:
                st.warning(f"Potenziale area da attenzionare: {alert}")
        else:
            st.info("Nessun alert automatico con i dati attuali.")

    with detail_tabs[1]:
        df = selected_snapshot["scope_df"]
        if df.empty:
            st.info("Nessuna scheda recente.")
        else:
            chart_df = df.melt(id_vars="data", value_vars=["ansia", "stress", "umore_intensita"], var_name="Indicatore", value_name="Valore")
            fig = px.line(chart_df, x="data", y="Valore", color="Indicatore", markers=True, range_y=[0, 10])
            fig.update_layout(xaxis_title="Data", yaxis_title="Intensità", legend_title="Indicatore")
            st.plotly_chart(fig, use_container_width=True)
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Trigger ricorrenti**")
                st.dataframe(most_common_values(df["trigger"], limit=5).rename("Frequenza"), use_container_width=True)
            with col_b:
                st.markdown("**Pensieri automatici recenti**")
                recent_thoughts = df["pensiero_automatico"].dropna().tail(5)
                st.write("\n".join(f"- {thought}" for thought in recent_thoughts if str(thought).strip()) or "Nessun pensiero inserito.")

    with detail_tabs[2]:
        st.markdown("### Assegna homework CBT")
        with st.form("assign_homework"):
            template_name = st.selectbox("Template CBT", list(CBT_HOMEWORK_TEMPLATES.keys()))
            template = CBT_HOMEWORK_TEMPLATES[template_name]
            st.caption(template["obiettivo"])
            due_date = st.date_input("Scadenza", value=date.today())
            instructions = st.text_area(
                "Nota o contesto per il paziente (facoltativo)",
                placeholder="Es. dopo una situazione sociale, dopo un episodio di ansia, prima della prossima seduta.",
                height=80,
            )
            default_questions = homework_questions_for(template_name)
            st.markdown("**Domande mostrate al paziente**")
            question_1 = st.text_area("Domanda principale", value=default_questions[0], height=70)
            question_2 = st.text_input("Domanda 2", value=default_questions[1] if len(default_questions) > 1 else "")
            question_3 = st.text_input("Domanda 3", value=default_questions[2] if len(default_questions) > 2 else "")
            if st.form_submit_button("Assegna al paziente", use_container_width=True):
                questions = [question for question in [clean_text(question_1), clean_text(question_2), clean_text(question_3)] if question]
                selected_wellness["homework_assignments"].append({
                    "id": f"hw_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    "template": template_name,
                    "objective": template["obiettivo"],
                    "instructions": instructions,
                    "questions": questions or homework_questions_for(template_name),
                    "due_date": due_date.isoformat(),
                    "assigned_at": datetime.utcnow().isoformat(timespec="seconds"),
                    "assigned_by": username,
                })
                save_wellness_for(selected_username, selected_wellness)
                st.success("Homework assegnato.")
                st.rerun()
        assignments = selected_wellness.get("homework_assignments", [])
        submissions = selected_wellness.get("homework_submissions", [])
        completed_ids = {submission.get("assignment_id") for submission in submissions}
        st.markdown("### Andamento e compliance")
        st.metric("Completati", f"{selected_snapshot['homework_completed']} / {selected_snapshot['homework_total']}")
        if assignments:
            st.markdown("#### Homework assegnati")
            st.dataframe(pd.DataFrame(homework_assignment_rows(assignments, completed_ids)), use_container_width=True, hide_index=True)
        if submissions:
            st.markdown("#### Risposte del paziente")
            for submission in sorted(submissions, key=lambda item: item.get("submitted_at", ""), reverse=True):
                with st.expander(f"{submission.get('template', 'Homework')} · {submission.get('submitted_at', '—')}", expanded=True):
                    if clean_text(submission.get("summary")):
                        st.markdown("**Nota per la seduta**")
                        st.write(submission.get("summary"))
                    render_homework_answers(submission)
        else:
            st.info("Il paziente non ha ancora inviato risposte agli homework.")

    with detail_tabs[3]:
        st.markdown("### Timeline terapeutica condivisa")
        events = build_timeline_events(selected_wellness)
        if not events:
            st.info("La timeline si popolerà con diario, homework ed eventi.")
        for event in events[:30]:
            st.markdown(f"**{event.get('data', '—')} · {event.get('tipo', 'Evento')}**")
            st.write(f"{event.get('titolo', '')} — {event.get('dettaglio', '')}")
        with st.form("manual_timeline_event"):
            event_title = st.text_input("Aggiungi evento/progresso/ricaduta")
            event_detail = st.text_area("Dettaglio")
            if st.form_submit_button("Aggiungi alla timeline", use_container_width=True):
                selected_wellness["timeline_events"].append({
                    "data": datetime.utcnow().isoformat(timespec="seconds"),
                    "tipo": "Evento clinico",
                    "titolo": event_title,
                    "dettaglio": event_detail,
                })
                save_wellness_for(selected_username, selected_wellness)
                st.success("Evento aggiunto.")
                st.rerun()

    with detail_tabs[4]:
        st.markdown("### Note private terapeuta")
        st.caption("Queste note restano nello spazio del professionista e non sono mostrate al paziente.")
        notes = load_therapist_notes(username)
        note_value = notes.get(selected_username, "")
        updated_note = st.text_area("Osservazioni cliniche, ipotesi, note seduta", value=note_value, height=260)
        if st.button("Salva note private", use_container_width=True):
            notes[selected_username] = updated_note
            save_therapist_notes(username, notes)
            st.success("Note private salvate.")

    with detail_tabs[5]:
        st.markdown("### Riassunto automatico pre-seduta")
        recap = weekly_recap(selected_snapshot)
        st.text_area("Ultimi 14 giorni", value="\n".join(f"- {item}" for item in recap), height=260)
        st.download_button(
            "Scarica recap .txt",
            data="\n".join(recap),
            file_name=f"recap_{selected_username}.txt",
            mime="text/plain",
            use_container_width=True,
        )


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
ensure_wellness_schema(st.session_state.wellness)

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
app_tabs = st.tabs(["💬 Chat", "📝 Diario CBT", "📚 Homework CBT", "📈 Monitoraggio", "📋 Resoconto"])
with app_tabs[0]:
    show_chat_tab()
with app_tabs[1]:
    show_diary_tab()
with app_tabs[2]:
    show_homework_tab()
with app_tabs[3]:
    show_monitoring_tab()
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
