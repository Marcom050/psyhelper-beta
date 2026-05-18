from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_groq import ChatGroq

from services.llm_prompt_service import build_llm_system_prompt
from services.clinical_analysis_service import (
    build_timeline_events,
    clinical_snapshot,
    most_common_values,
    weekly_recap,
)
from services.auth_service import (
    client_accounts_for,
    create_client_account,
    create_user,
    default_wellness_data,
    ensure_wellness_schema,
    is_valid_email,
    load_account_bundle,
    load_user_metadata,
    load_therapist_notes,
    normalize_email,
    normalize_username,
    save_account_bundle,
    save_wellness_for,
    save_therapist_notes,
    therapist_email_exists,
    user_exists,
    verify_password,
)
from services.subscription_service import (
    BETA_TRIAL_DAYS,
    is_subscription_active_for,
    is_trial_expired,
    trial_days_remaining,
    trial_expires_at,
)

st.set_page_config(page_title="PsyHelper", page_icon="🧠", layout="wide")

ANALYTICS_ID = "G-KWR24JLV0Y"
COPYRIGHT_POLICY = """
Policy copyright: non riprodurre o continuare testi protetti da copyright non forniti dall'utente, inclusi brani di libri, articoli, canzoni, manuali o materiali formativi.
Se l'utente chiede contenuti protetti estesi, rifiuta brevemente la riproduzione e offri invece riassunti, spiegazioni, parafrasi brevi, analisi o indicazioni originali.
Se l'utente fornisce personalmente un breve estratto, puoi commentarlo o trasformarlo limitando le citazioni testuali allo stretto necessario.
"""

BETA_DISCLAIMER_TEXT = """
Questa è una versione di prova di PsyHelper, concessa esclusivamente per finalità di beta test.
Non deve essere usata con clienti reali, non deve trattare dati personali, sanitari, clinici o comunque riferibili a clienti/pazienti reali e non sostituisce strumenti professionali validati o obblighi deontologici, legali e privacy.

L'autore declina ogni tipo di responsabilità per qualsiasi uso improprio dell'applicazione, dei suoi contenuti o delle indicazioni generate.

Questa applicazione è protetta dalla normativa sul diritto d’autore ai sensi della Legge sul diritto d'autore e successive modifiche. Tutti i diritti sono riservati. È vietata la riproduzione, distribuzione, modifica, pubblicazione, comunicazione o condivisione totale o parziale dell’applicazione e dei suoi contenuti senza preventiva autorizzazione del titolare dei diritti, salvo i casi consentiti dalla legge.
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

if not st.session_state.get("beta_disclaimer_accepted", False):
    st.warning("Prima di usare o creare un account devi accettare le condizioni della versione di prova.")
    st.markdown("### Scarico di responsabilità e diritto d'autore")
    st.info(BETA_DISCLAIMER_TEXT)
    accepted = st.checkbox(
        "Ho letto e accetto: userò PsyHelper solo per beta test, senza clienti reali, senza dati di clienti/pazienti reali e assumendomi la responsabilità di non farne uso improprio.",
        key="beta_disclaimer_acceptance_checkbox",
    )
    if st.button("Accetta e continua", use_container_width=True, disabled=not accepted):
        st.session_state.beta_disclaimer_accepted = True
        st.session_state.beta_disclaimer_accepted_at = datetime.utcnow().isoformat(timespec="seconds")
        st.rerun()
    st.stop()

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
    "Respiro 3 minuti": {
        "obiettivo": "Ridurre l'attivazione fisica dell'ansia con una pausa breve e ripetibile.",
        "campi": ["Fallo una volta. Ansia prima/dopo 0-10 e una parola su com'è andata."],
        "suggerimento": "Adatto per ansia, tensione e momenti di blocco.",
    },
    "Pensiero più realistico": {
        "obiettivo": "Allenare una risposta più equilibrata a un pensiero ansioso o insicuro.",
        "campi": ["Scrivi: pensiero difficile + risposta più realistica."],
        "suggerimento": "Utile per ruminazione, catastrofismo e autocritica.",
    },
    "Piccolo passo evitato": {
        "obiettivo": "Ridurre l'evitamento con un'azione piccola, sicura e concreta.",
        "campi": ["Fai un passo di 5 minuti che stavi evitando. Scrivi quale."],
        "suggerimento": "Utile quando ansia o insicurezza portano a rimandare.",
    },
    "Tempo per le preoccupazioni": {
        "obiettivo": "Contenere i pensieri ripetitivi dando loro uno spazio limitato.",
        "campi": ["Dedica 10 minuti alle preoccupazioni. Scrivi solo le 2 principali."],
        "suggerimento": "Utile per sovrappensieri, stress e rimuginio serale.",
    },
    "Azione di cura": {
        "obiettivo": "Inserire un gesto semplice che sostenga energia, calma o autostima.",
        "campi": ["Fai una cosa gentile per te. Scrivi cosa e umore dopo 0-10."],
        "suggerimento": "Utile per stress, stanchezza e svalutazione di sé.",
    },
    "Nota per la seduta": {
        "obiettivo": "Tenere traccia di un punto importante da portare in colloquio.",
        "campi": ["Scrivi una cosa importante da ricordare in seduta."],
        "suggerimento": "Da usare quando serve una nota libera e breve.",
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


def active_subscription_statuses():
    configured_statuses = st.secrets.get("ACTIVE_SUBSCRIPTION_STATUSES", "active,trialing")
    return {status.strip().lower() for status in configured_statuses.split(",") if status.strip()}


def has_active_subscription(username):
    return is_subscription_active_for(username, active_subscription_statuses())


def load_user_data(username):
    bundle = load_account_bundle(username)
    st.session_state.user_metadata = load_user_metadata(username)
    st.session_state.profile = bundle["profile"]
    st.session_state.messages = bundle["messages"]
    st.session_state.wellness = bundle["wellness"]


def save_user_data(username):
    save_account_bundle(
        username,
        st.session_state.profile,
        st.session_state.messages,
        st.session_state.get("wellness", default_wellness_data()),
    )


def get_response(user_input):
    profile = st.session_state.get("profile", {})
    wellness = st.session_state.get("wellness", default_wellness_data())
    system_prompt = build_llm_system_prompt(profile, wellness, COPYRIGHT_POLICY)

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


def clean_text(value):
    return str(value or "").strip()


def homework_questions_for(template_name, assignment=None):
    assignment = assignment or {}
    custom_questions = [clean_text(question) for question in assignment.get("questions", [])]
    custom_questions = [question for question in custom_questions if question]
    if custom_questions:
        return custom_questions
    template = CBT_HOMEWORK_TEMPLATES.get(template_name, {})
    return template.get("campi", ["Scrivi qui la tua risposta"])


def homework_main_prompt(template_name, assignment=None):
    questions = homework_questions_for(template_name, assignment)
    return questions[0] if questions else "Scrivi qui la tua risposta"


def homework_answer_items(answers):
    if isinstance(answers, dict):
        return [(clean_text(question), clean_text(answer)) for question, answer in answers.items() if clean_text(answer)]
    if isinstance(answers, list):
        return [(f"Risposta {index}", clean_text(answer)) for index, answer in enumerate(answers, start=1) if clean_text(answer)]
    answer = clean_text(answers)
    return [("Risposta", answer)] if answer else []


def homework_readable_summary(submission, max_chars=180):
    summary = clean_text(submission.get("summary"))
    answer_items = homework_answer_items(submission.get("answers", {}))
    readable = summary or (" · ".join(answer for _, answer in answer_items[:2]) if answer_items else "Nessuna risposta inserita.")
    return readable if len(readable) <= max_chars else f"{readable[:max_chars].rstrip()}…"


def homework_template_label(template_name):
    return template_name


def assignment_status(assignment, completed_ids):
    if assignment.get("id") in completed_ids or assignment.get("status") == "completato":
        return "Completato"
    due = clean_text(assignment.get("due_date"))
    if due:
        try:
            if date.fromisoformat(due) < date.today():
                return "Scaduto"
        except ValueError:
            pass
    return "Da completare"


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
            "stato": assignment_status(assignment, completed_ids),
            "consegna": homework_main_prompt(assignment.get("template", "Homework"), assignment),
        })
    return rows


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
    st.caption(
        "Compiti CBT rapidi per monitorare la qualità della vita tra le sedute: "
        "una consegna chiara, una risposta essenziale, invio immediato al terapeuta."
    )
    ensure_wellness_schema(st.session_state.wellness)

    assignments = st.session_state.wellness["homework_assignments"]
    submissions = st.session_state.wellness["homework_submissions"]
    completed_ids = {submission.get("assignment_id") for submission in submissions}
    open_assignments = [assignment for assignment in assignments if assignment.get("id") not in completed_ids]

    if open_assignments:
        st.markdown("### Da completare")
        selected_assignment = st.selectbox(
            "Scegli il compito",
            open_assignments,
            format_func=lambda item: f"{item.get('template', 'Homework')} · {assignment_status(item, completed_ids).lower()} · scadenza {item.get('due_date', 'non indicata')}",
        )
        template_name = selected_assignment.get("template")
        template = CBT_HOMEWORK_TEMPLATES.get(template_name, {})
        prompt = homework_main_prompt(template_name, selected_assignment)
        info_col, due_col = st.columns([3, 1])
        with info_col:
            st.info(template.get("obiettivo") or "Compito breve assegnato dal terapeuta.")
        with due_col:
            st.metric("Scadenza", selected_assignment.get("due_date", "—"))
        with st.form("assigned_homework_submission"):
            answer = st.text_area(
                prompt,
                key=f"assigned_{selected_assignment.get('id')}_single_answer",
                height=150,
                placeholder="Scrivi una risposta breve.",
            )
            if st.form_submit_button("Invia al terapeuta", use_container_width=True):
                submissions.append({
                    "assignment_id": selected_assignment.get("id"),
                    "template": template_name,
                    "submitted_at": datetime.utcnow().isoformat(timespec="seconds"),
                    "answers": {prompt: answer},
                    "summary": homework_readable_summary({"answers": {prompt: answer}}, max_chars=140),
                })
                save_user_data(st.session_state.username)
                st.success("Homework inviato. Il terapeuta vedrà solo la sintesi e la risposta essenziale.")
                st.rerun()
    else:
        st.info("Non ci sono homework assegnati aperti. Puoi comunque salvare un check-in breve da portare in seduta.")

    with st.expander("➕ Check-in o nota libera", expanded=not open_assignments):
        selected = st.selectbox(
            "Tipo di check-in",
            list(CBT_HOMEWORK_TEMPLATES.keys()),
            format_func=homework_template_label,
        )
        template = CBT_HOMEWORK_TEMPLATES[selected]
        prompt = homework_main_prompt(selected)
        st.markdown(f"**A cosa serve:** {template['obiettivo']}")
        with st.form("free_homework_submission"):
            answer = st.text_area(
                prompt,
                key=f"free_{selected}_single_answer",
                height=150,
                placeholder="Scrivi una risposta breve.",
            )
            if st.form_submit_button("Salva per la seduta", use_container_width=True):
                submissions.append({
                    "assignment_id": None,
                    "template": selected,
                    "submitted_at": datetime.utcnow().isoformat(timespec="seconds"),
                    "answers": {prompt: answer},
                    "summary": homework_readable_summary({"answers": {prompt: answer}}, max_chars=140),
                })
                save_user_data(st.session_state.username)
                st.success("Check-in salvato.")

    if submissions:
        with st.expander("Storico essenziale homework e note"):
            rows = [
                {
                    "data": item.get("submitted_at"),
                    "homework": item.get("template"),
                    "sintesi": homework_readable_summary(item),
                }
                for item in sorted(submissions, key=lambda item: item.get("submitted_at", ""), reverse=True)
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
    metadata = load_user_metadata(therapist_username or account_label)
    if is_trial_expired(metadata):
        st.error(
            "Il periodo di prova gratuito di 7 giorni è scaduto: l'account è bloccato "
            "e non può usare PsyHelper finché non viene riattivato dal titolare del servizio."
        )
        st.caption(f"Scadenza prova: {trial_expires_at(metadata.get('created_at')).strftime('%d/%m/%Y %H:%M UTC')}")
    else:
        st.warning(
            "Per usare PsyHelper serve un abbonamento professionale attivo o una prova beta valida. "
            "Gli account cliente sono coperti dallo stato dello psicologo che li ha creati."
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




@st.dialog("➕ Crea nuovo paziente")
def show_create_patient_dialog(therapist_username):
    st.caption("Inserisci solo i dati essenziali. Il profilo comparirà subito nell'elenco pazienti.")
    with st.form("create_client_account_dialog"):
        client_name = st.text_input("Nome paziente", placeholder="Es. Mario Rossi")
        client_username = st.text_input("Username paziente", placeholder="mario_rossi")
        client_password = st.text_input("Password temporanea", type="password")
        confirm_client_password = st.text_input("Conferma password temporanea", type="password")
        submitted = st.form_submit_button("Crea paziente", use_container_width=True)

    if not submitted:
        return

    normalized_client_username = normalize_username(client_username)
    if not client_name.strip():
        st.error("Inserisci il nome del paziente.")
    elif len(normalized_client_username) < 3:
        st.error("Lo username paziente deve avere almeno 3 caratteri.")
    elif user_exists(normalized_client_username):
        st.error("Username paziente già esistente.")
    elif len(client_password) < 8:
        st.error("La password temporanea deve avere almeno 8 caratteri.")
    elif client_password != confirm_client_password:
        st.error("Le password non coincidono.")
    else:
        create_client_account(therapist_username, normalized_client_username, client_password, client_name.strip())
        st.session_state.selected_patient_username = normalized_client_username
        st.success(f"Profilo paziente `{normalized_client_username}` creato.")
        st.rerun()


@st.dialog("👥 Scegli profilo paziente")
def show_patient_selector_dialog(clients, snapshots, overview_rows):
    st.caption("Seleziona il profilo paziente da aprire nella dashboard. La scheda scelta verrà mostrata a tutta larghezza.")
    search_term = st.text_input("Cerca per nome o username", placeholder="Es. mario", key="patient_selector_search").strip().lower()

    visible_clients = [
        client for client in clients
        if not search_term
        or search_term in str(client.get("nome", "")).lower()
        or search_term in str(client.get("username", "")).lower()
    ]

    if not visible_clients:
        st.info("Nessun profilo corrisponde alla ricerca.")
    else:
        for client in visible_clients:
            snapshot = snapshots[client["username"]]
            is_selected = client["username"] == st.session_state.get("selected_patient_username")
            label = f"{'✅ Profilo attivo' if is_selected else 'Apri profilo'} · {client['nome']}"
            if st.button(label, key=f"select_patient_dialog_{client['username']}", use_container_width=True):
                st.session_state.selected_patient_username = client["username"]
                st.rerun()
            st.caption(
                f"@{client['username']} · ultima attività: {snapshot['last_activity']} · "
                f"alert: {len(snapshot['alerts'])} · homework: {snapshot['homework_completed']}/{snapshot['homework_total']}"
            )

    with st.expander("Mostra tabella riepilogo", expanded=False):
        st.dataframe(pd.DataFrame(overview_rows), use_container_width=True, hide_index=True)


def show_therapist_dashboard():
    username = st.session_state.username
    metadata = st.session_state.get("user_metadata", load_user_metadata(username))
    subscription_status = metadata.get("subscription_status", "inactive")
    subscription_active = has_active_subscription(username)

    st.header("👩‍⚕️ Dashboard terapeuta intelligente")
    st.caption("Focus clinico: overview pazienti, insight automatici, aderenza, alert e organizzazione del materiale per la seduta.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Accesso", "Attivo" if subscription_active else "Bloccato")
    col2.metric("Stato", subscription_status)
    if subscription_status.lower() == "trialing":
        col3.metric("Giorni prova rimasti", trial_days_remaining(metadata.get("created_at")))
    else:
        col3.metric("Account", metadata.get("email") or username)

    if not subscription_active:
        show_subscription_required(username)
        return

    clients = client_accounts_for(username)

    create_col, _ = st.columns([1, 4])
    with create_col:
        if st.button("➕ Crea nuovo paziente", use_container_width=True):
            show_create_patient_dialog(username)

    clients = client_accounts_for(username)
    if not clients:
        st.info("Non hai ancora creato profili paziente. Usa il pulsante ➕ Crea nuovo paziente per aggiungere il primo profilo.")
        return

    overview_rows = []
    bundles = {}
    snapshots = {}
    for client in clients:
        bundle = load_account_bundle(client["username"])
        bundles[client["username"]] = bundle
        snapshot = clinical_snapshot(bundle["wellness"], bundle["messages"])
        snapshots[client["username"]] = snapshot
        overview_rows.append({
            "paziente": client["nome"],
            "username": client["username"],
            "ultima attività": snapshot["last_activity"],
            "ansia media 14g": f"{snapshot['avg_anxiety']:.1f}/10",
            "stress medio 14g": f"{snapshot['avg_stress']:.1f}/10",
            "homework": f"{snapshot['homework_completed']}/{snapshot['homework_total']}",
            "alert": len(snapshot["alerts"]),
            "insight principale": snapshot["insights"][0],
        })

    patient_usernames = [client["username"] for client in clients]
    if st.session_state.get("selected_patient_username") not in patient_usernames:
        st.session_state.selected_patient_username = patient_usernames[0]

    selected_username = st.session_state.selected_patient_username
    selected_bundle = bundles[selected_username]
    selected_profile = selected_bundle["profile"]
    selected_wellness = selected_bundle["wellness"]
    selected_snapshot = clinical_snapshot(selected_wellness, selected_bundle["messages"])

    selected_patient_name = selected_profile.get("nome", selected_username)
    selector_col, active_col = st.columns([1, 3], gap="large")
    with selector_col:
        if st.button("👥 Scegli profilo paziente", use_container_width=True):
            show_patient_selector_dialog(clients, snapshots, overview_rows)
    with active_col:
        st.info(
            f"Profilo attivo: **{selected_patient_name}** (`@{selected_username}`) · "
            f"ultima attività: {selected_snapshot['last_activity']} · "
            f"alert: {len(selected_snapshot['alerts'])} · "
            f"homework: {selected_snapshot['homework_completed']}/{selected_snapshot['homework_total']}"
        )

    st.markdown(f"## {selected_patient_name}")
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
        st.markdown("### Homework CBT qualità di vita")
        st.caption("Assegna un compito essenziale: modello, scadenza e una consegna già pronta. Il controllo mostra subito stato e sintesi.")
        assignments = selected_wellness.get("homework_assignments", [])
        submissions = selected_wellness.get("homework_submissions", [])
        completed_ids = {submission.get("assignment_id") for submission in submissions}

        assign_col, monitor_col = st.columns([1, 1])
        with assign_col:
            with st.form("assign_homework"):
                template_name = st.selectbox(
                    "Compito CBT",
                    list(CBT_HOMEWORK_TEMPLATES.keys()),
                    format_func=homework_template_label,
                )
                due_date = st.date_input("Scadenza", value=date.today())
                template = CBT_HOMEWORK_TEMPLATES[template_name]
                st.markdown(f"**Obiettivo:** {template['obiettivo']}")
                if clean_text(template.get("suggerimento")):
                    st.caption(template["suggerimento"])
                prompt = st.text_area(
                    "Consegna essenziale",
                    value=homework_main_prompt(template_name),
                    height=95,
                    placeholder="Mantieni una sola traccia: il paziente risponderà in un unico spazio.",
                )
                if st.form_submit_button("Assegna", use_container_width=True):
                    final_prompt = clean_text(prompt) or homework_main_prompt(template_name)
                    selected_wellness["homework_assignments"].append({
                        "id": f"hw_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                        "template": template_name,
                        "objective": template["obiettivo"],
                        "instructions": clean_text(template.get("suggerimento")),
                        "questions": [final_prompt],
                        "due_date": due_date.isoformat(),
                        "assigned_at": datetime.utcnow().isoformat(timespec="seconds"),
                        "assigned_by": username,
                    })
                    save_wellness_for(selected_username, selected_wellness)
                    st.success("Homework assegnato.")
                    st.rerun()

        with monitor_col:
            st.metric("Completati", f"{selected_snapshot['homework_completed']} / {selected_snapshot['homework_total']}")
            if assignments:
                st.dataframe(pd.DataFrame(homework_assignment_rows(assignments, completed_ids)), use_container_width=True, hide_index=True)
            else:
                st.info("Nessun homework assegnato.")

        if submissions:
            st.markdown("#### Ultime risposte")
            response_rows = [
                {
                    "data": submission.get("submitted_at", "—"),
                    "homework": submission.get("template", "Homework"),
                    "sintesi": homework_readable_summary(submission),
                }
                for submission in sorted(submissions, key=lambda item: item.get("submitted_at", ""), reverse=True)
            ]
            st.dataframe(pd.DataFrame(response_rows), use_container_width=True, hide_index=True)
            with st.expander("Apri risposte complete", expanded=False):
                for submission in sorted(submissions, key=lambda item: item.get("submitted_at", ""), reverse=True):
                    st.markdown(f"**{submission.get('template', 'Homework')} · {submission.get('submitted_at', '—')}**")
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

def reset_session_for_logout():
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.user_metadata = {}
    st.session_state.profile = {}
    st.session_state.messages = []
    st.session_state.wellness = default_wellness_data()
    st.session_state.scroll_to_top = True


def logout_button():
    if st.button("Logout", use_container_width=True):
        reset_session_for_logout()
        st.rerun()


def render_login_form():
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


def render_therapist_signup_form():
    st.info(
        f"Crea l'account professionista per una prova beta di {BETA_TRIAL_DAYS} giorni. "
        "Ogni email può creare un solo account psicologo e l'app non deve essere usata con clienti reali."
    )
    with st.form("therapist_signup"):
        professional_name = st.text_input("Nome professionista o studio")
        professional_email = st.text_input("Email professionale obbligatoria")
        new_username = st.text_input("Scegli un nome utente professionista")
        new_password = st.text_input("Scegli una password", type="password")
        confirm_password = st.text_input("Conferma password", type="password")
        if st.form_submit_button("Crea account professionista", use_container_width=True):
            normalized_username = normalize_username(new_username)
            initial_status = "trialing"
            normalized_email = normalize_email(professional_email)
            if not professional_name.strip():
                st.error("Inserisci il nome del professionista o dello studio.")
            elif not is_valid_email(normalized_email):
                st.error("Inserisci un indirizzo email valido per l'account psicologo.")
            elif therapist_email_exists(normalized_email):
                st.error("Esiste già un account psicologo associato a questa email.")
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
                    profile={"nome": professional_name.strip(), "email": normalized_email, "account_type": "therapist"},
                    email=normalized_email,
                    beta_disclaimer_accepted_at=st.session_state.get(
                        "beta_disclaimer_accepted_at", datetime.utcnow().isoformat(timespec="seconds")
                    ),
                )
                st.success(
                    f"Account professionista creato. La prova beta dura {BETA_TRIAL_DAYS} giorni dalla creazione; "
                    "ora effettua il login."
                )


def render_login_area():
    tab1, tab2 = st.tabs(["Login", "Registrati come psicologo"])
    with tab1:
        render_login_form()
    with tab2:
        render_therapist_signup_form()


def initialize_authenticated_session():
    if st.session_state.pop("scroll_to_top", False):
        scroll_to_top()

    st.session_state.setdefault("profile", {})
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("wellness", default_wellness_data())
    st.session_state.setdefault("user_metadata", load_user_metadata(st.session_state.username))
    if not isinstance(st.session_state.wellness, dict):
        st.session_state.wellness = default_wellness_data()
    ensure_wellness_schema(st.session_state.wellness)


def ensure_subscription_or_stop(current_metadata):
    if has_active_subscription(st.session_state.username):
        return

    show_subscription_required(st.session_state.username, current_metadata.get("therapist_username"))
    st.divider()
    logout_button()
    st.stop()



def render_onboarding_or_stop():
    if st.session_state.profile.get("onboarding_completed", False):
        return

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


def render_client_app_tabs():
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


def render_client_footer_actions():
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
            reset_session_for_logout()
            st.rerun()


def render_authenticated_app():
    initialize_authenticated_session()

    current_metadata = st.session_state.get("user_metadata", {})
    current_role = current_metadata.get("role", "client")

    if current_role == "therapist":
        show_therapist_dashboard()
        st.divider()
        logout_button()
        st.stop()

    ensure_subscription_or_stop(current_metadata)
    render_onboarding_or_stop()
    render_client_app_tabs()
    render_client_footer_actions()


# ====================== LOGIN ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    render_login_area()
    st.stop()

render_authenticated_app()
