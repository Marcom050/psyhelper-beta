from datetime import date, datetime
import logging

import pandas as pd
import plotly.express as px
import streamlit as st
from clients import APIClientConfig, PsyHelperAPIClient
from clients.exceptions import APIClientError, APIHTTPError, APITimeoutError, APIUnauthorizedError
from services.chat_service import ChatContext, get_response as get_chat_response
from services.report_service import (
    build_timeline_events,
    clinical_snapshot,
    mood_entries_dataframe,
    most_common_values,
    weekly_recap,
)
from services.homework_service import (
    CBT_HOMEWORK_TEMPLATES,
    append_assignment,
    append_submission,
    assignment_status,
    clean_text,
    completed_assignment_ids,
    create_assignment,
    create_submission,
    get_assigned_homework,
    get_open_assignments,
    get_submitted_homework,
    homework_answer_items,
    homework_assignment_rows,
    homework_main_prompt,
    homework_readable_summary,
    homework_template_label,
    submitted_homework_rows,
)
from services.auth_service import (
    client_accounts_for,
    create_client_account,
    create_user,
    ensure_wellness_schema,
    is_valid_email,
    load_account_bundle,
    load_user_metadata,
    load_therapist_notes,
    normalize_email,
    normalize_username,
    save_wellness_for,
    save_therapist_notes,
    therapist_email_exists,
    user_exists,
    verify_password,
)
from services.session_adapter import SessionAdapter
from services.subscription_service import (
    BETA_TRIAL_DAYS,
    is_subscription_active_for,
    is_trial_expired,
    trial_days_remaining,
    trial_expires_at,
)

LOGGER = logging.getLogger(__name__)

st.set_page_config(page_title="PsyHelper", page_icon="🧠", layout="wide")

session_adapter = SessionAdapter()
session_adapter.initialize_defaults()

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


def secret_get(key, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def render_analytics_banner():
    st.sidebar.markdown("### Privacy e analytics")
    st.sidebar.caption(
        "Google Analytics resta disattivato finché non dai consenso. "
        "Se attivato, vengono raccolte metriche d'uso aggregate; non inserire dati sensibili nei campi liberi se non necessario."
    )
    consent = st.sidebar.checkbox(
        "Acconsento all'uso di Google Analytics",
        value=session_adapter.get_analytics_consent(),
        key="analytics_consent_checkbox",
    )
    session_adapter.set_analytics_consent(consent)

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

if not session_adapter.is_beta_disclaimer_accepted():
    st.warning("Prima di usare o creare un account devi accettare le condizioni della versione di prova.")
    st.markdown("### Scarico di responsabilità e diritto d'autore")
    st.info(BETA_DISCLAIMER_TEXT)
    accepted = st.checkbox(
        "Ho letto e accetto: userò PsyHelper solo per beta test, senza clienti reali, senza dati di clienti/pazienti reali e assumendomi la responsabilità di non farne uso improprio.",
        key="beta_disclaimer_acceptance_checkbox",
    )
    if st.button("Accetta e continua", use_container_width=True, disabled=not accepted):
        session_adapter.accept_beta_disclaimer(datetime.utcnow().isoformat(timespec="seconds"))
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

GROQ_API_KEY = secret_get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    st.error("⚠️ API Key non configurata!")
    st.stop()


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


def api_client_config():
    return APIClientConfig.from_values(
        base_url=secret_get("API_BASE_URL", None),
        timeout_seconds=secret_get("API_TIMEOUT_SECONDS", None),
        use_http_api=secret_get("USE_HTTP_API", None),
    )


def use_http_api():
    return api_client_config().use_http_api


def api_client():
    return PsyHelperAPIClient(
        api_client_config(),
        access_token=session_adapter.get_access_token(),
        refresh_token=session_adapter.get_refresh_token(),
    )


def show_api_error(error):
    if isinstance(error, APIUnauthorizedError):
        st.error("Nome utente o password errati")
    elif isinstance(error, APITimeoutError):
        st.error("Il backend non risponde. Riprova tra poco o disattiva USE_HTTP_API per il fallback locale.")
    elif isinstance(error, APIHTTPError) and error.status_code == 404:
        st.error("Risorsa non trovata nel backend API.")
    else:
        st.error("Backend API non raggiungibile. Riprova tra poco o disattiva USE_HTTP_API per il fallback locale.")

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
    configured_statuses = secret_get("ACTIVE_SUBSCRIPTION_STATUSES", "active,trialing")
    return {status.strip().lower() for status in configured_statuses.split(",") if status.strip()}


def has_active_subscription(username):
    return is_subscription_active_for(username, active_subscription_statuses())


def load_user_data(username):
    if not use_http_api():
        session_adapter.load_user_session(username)
        return

    me_payload = api_client().me(username)
    wellness = api_client().get_wellness(username)
    local_bundle = load_account_bundle(username)
    session_adapter.set_user_metadata(me_payload["metadata"])
    session_adapter.set_profile(me_payload["profile"])
    session_adapter.set_messages(local_bundle["messages"])
    session_adapter.set_wellness(wellness)


def save_user_data(username):
    session_adapter.persist_user_session(username)


def replace_wellness(current_wellness, updated_wellness):
    current_wellness.clear()
    current_wellness.update(updated_wellness)


def homework_for(username, wellness):
    if not use_http_api():
        return get_assigned_homework(wellness), get_submitted_homework(wellness)
    try:
        payload = api_client().get_homework(username)
    except APIClientError as error:
        show_api_error(error)
        return get_assigned_homework(wellness), get_submitted_homework(wellness)
    return payload["assignments"], payload["submissions"]


def save_homework_submission_for(username, wellness, assignment_id, template, prompt, answer):
    if not use_http_api():
        append_submission(wellness, create_submission(assignment_id, template, prompt, answer))
        save_user_data(username)
        return True
    try:
        response = api_client().create_homework_submission(
            username,
            {
                "assignment_id": assignment_id,
                "template": template,
                "prompt": prompt,
                "answer": answer,
            },
        )
    except APIClientError as error:
        show_api_error(error)
        return False
    session_adapter.set_wellness(response["wellness"])
    return True


def assign_homework_for(client_username, therapist_username, wellness, template_name, due_date, prompt):
    if not use_http_api():
        assignment = create_assignment(template_name, due_date, therapist_username, prompt=prompt)
        append_assignment(wellness, assignment)
        save_wellness_for(client_username, wellness)
        return True
    try:
        response = api_client().create_homework_assignment(
            client_username,
            {
                "template": template_name,
                "due_date": due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date),
                "assigned_by": therapist_username,
                "prompt": prompt,
            },
        )
    except APIClientError as error:
        show_api_error(error)
        return False
    replace_wellness(wellness, response["wellness"])
    return True


def clinical_report_for(username, wellness, messages):
    if not use_http_api():
        return clinical_snapshot(wellness, messages)
    try:
        report = api_client().get_clinical_report(username)["report"]
    except APIClientError as error:
        show_api_error(error)
        return clinical_snapshot(wellness, messages)
    report["scope_df"] = mood_entries_dataframe(wellness)
    return report


def weekly_recap_payload_for(username, report):
    if not use_http_api():
        recap = weekly_recap(report)
        return {"display_text": recap.to_text(bullet_prefix="- "), "download_text": recap.to_text()}
    try:
        payload = api_client().get_weekly_recap(username)
    except APIClientError as error:
        show_api_error(error)
        recap = weekly_recap(report)
        return {"display_text": recap.to_text(bullet_prefix="- "), "download_text": recap.to_text()}
    return {"display_text": payload["text"], "download_text": "\n".join(payload["items"])}


def chat_context_for(user_input):
    return ChatContext(
        profile=session_adapter.get_profile(),
        wellness=session_adapter.get_wellness(),
        username=session_adapter.get_username() or "",
        user_input=user_input,
    )


def get_local_chat_response(context):
    return get_chat_response(
        context,
        api_key=GROQ_API_KEY,
        copyright_policy=COPYRIGHT_POLICY,
    ).content


def get_http_chat_response(context):
    payload = api_client().chat_message(
        context.username,
        context.user_input,
        dict(context.profile),
        dict(context.wellness),
    )
    return payload["content"]


def get_response(user_input):
    context = chat_context_for(user_input)
    if not use_http_api():
        return get_local_chat_response(context)
    try:
        return get_http_chat_response(context)
    except APIClientError as error:
        LOGGER.warning("Chat API failed; falling back to local chat service: %s", error)
        return get_local_chat_response(context)


def entries_dataframe():
    return mood_entries_dataframe(session_adapter.get_wellness())


def render_homework_answers(submission):
    answer_items = homework_answer_items(submission.get("answers", {}))
    if not answer_items:
        st.info("Nessuna risposta inserita.")
        return
    for question, answer in answer_items:
        st.markdown(f"**{question}**")
        st.write(answer)
def show_chat_tab():
    st.markdown(f"<p class='subtitle'>Ciao {session_adapter.get_profile().get('nome', session_adapter.get_username())}</p>", unsafe_allow_html=True)

    for msg in session_adapter.get_messages():
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Descrivi cosa stai provando o quale esperienza vuoi approfondire..."):
        session_adapter.get_messages().append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            with st.spinner("Sto pensando..."):
                reply = get_response(user_input)
                st.markdown(reply)
                session_adapter.get_messages().append({"role": "assistant", "content": reply})
        save_user_data(session_adapter.get_username())


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
            if use_http_api():
                try:
                    response = api_client().create_mood_entry(session_adapter.get_username(), entry)
                    session_adapter.set_wellness(response["wellness"])
                except APIClientError as error:
                    show_api_error(error)
                    return
            else:
                session_adapter.get_wellness()["mood_entries"].append(entry)
                save_user_data(session_adapter.get_username())
            st.success("Scheda salvata. La trovi nel monitoraggio e nel resoconto.")


def show_monitoring_tab():
    st.subheader("📈 Monitoraggio ansia e stress")
    df = entries_dataframe()
    if df.empty:
        st.info("Aggiungi almeno una scheda nel diario per vedere trend e indicatori.")
        return

    snapshot = clinical_snapshot(session_adapter.get_wellness(), session_adapter.get_messages())
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
    ensure_wellness_schema(session_adapter.get_wellness())

    assignments, submissions = homework_for(session_adapter.get_username(), session_adapter.get_wellness())
    completed_ids = completed_assignment_ids(submissions)
    open_assignments = get_open_assignments(assignments, submissions)

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
                if save_homework_submission_for(
                    session_adapter.get_username(),
                    session_adapter.get_wellness(),
                    selected_assignment.get("id"),
                    template_name,
                    prompt,
                    answer,
                ):
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
                if save_homework_submission_for(
                    session_adapter.get_username(),
                    session_adapter.get_wellness(),
                    None,
                    selected,
                    prompt,
                    answer,
                ):
                    st.success("Check-in salvato.")

    if submissions:
        with st.expander("Storico essenziale homework e note"):
            rows = submitted_homework_rows(submissions, display_defaults=False)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

def show_report_tab():
    st.subheader("📋 Resoconto per colloqui psicologici")
    report = clinical_report_for(session_adapter.get_username(), session_adapter.get_wellness(), session_adapter.get_messages())
    report_scope_df = report["scope_df"]
    if report_scope_df.empty:
        st.info("Quando avrai salvato alcune schede, qui comparirà un resoconto sintetico esportabile.")
        return

    st.text_area("Resoconto sintetico", value=report["export_text"], height=360)
    st.download_button("Scarica resoconto .txt", data=report["export_text"], file_name="resoconto_psyhelper.txt", mime="text/plain", use_container_width=True)

    with st.expander("Vedi schede dettagliate"):
        st.dataframe(report_scope_df.sort_values("data", ascending=False), use_container_width=True)


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

    checkout_url = secret_get("SUBSCRIPTION_CHECKOUT_URL", "")
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
        session_adapter.set_selected_patient_username(normalized_client_username)
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
            is_selected = client["username"] == session_adapter.get_selected_patient_username()
            label = f"{'✅ Profilo attivo' if is_selected else 'Apri profilo'} · {client['nome']}"
            if st.button(label, key=f"select_patient_dialog_{client['username']}", use_container_width=True):
                session_adapter.set_selected_patient_username(client["username"])
                st.rerun()
            st.caption(
                f"@{client['username']} · ultima attività: {snapshot['last_activity']} · "
                f"alert: {len(snapshot['alerts'])} · homework: {snapshot['homework_completed']}/{snapshot['homework_total']}"
            )

    with st.expander("Mostra tabella riepilogo", expanded=False):
        st.dataframe(pd.DataFrame(overview_rows), use_container_width=True, hide_index=True)


def show_therapist_dashboard():
    username = session_adapter.get_username()
    metadata = session_adapter.get_user_metadata() or load_user_metadata(username)
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
        snapshot = clinical_report_for(client["username"], bundle["wellness"], bundle["messages"])
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
    if session_adapter.get_selected_patient_username() not in patient_usernames:
        session_adapter.set_selected_patient_username(patient_usernames[0])

    selected_username = session_adapter.get_selected_patient_username()
    selected_bundle = bundles[selected_username]
    selected_profile = selected_bundle["profile"]
    selected_wellness = selected_bundle["wellness"]
    selected_snapshot = clinical_report_for(selected_username, selected_wellness, selected_bundle["messages"])

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
        assignments, submissions = homework_for(selected_username, selected_wellness)
        completed_ids = completed_assignment_ids(submissions)

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
                    if assign_homework_for(selected_username, username, selected_wellness, template_name, due_date, prompt):
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
            response_rows = submitted_homework_rows(submissions)
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
        recap_payload = weekly_recap_payload_for(selected_username, selected_snapshot)
        st.text_area("Ultimi 14 giorni", value=recap_payload["display_text"], height=260)
        st.download_button(
            "Scarica recap .txt",
            data=recap_payload["download_text"],
            file_name=f"recap_{selected_username}.txt",
            mime="text/plain",
            use_container_width=True,
        )

def reset_session_for_logout():
    session_adapter.reset_for_logout()


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
            if use_http_api():
                try:
                    login_payload = api_client().login(normalized_username, password)
                    session_adapter.set_logged_in(True)
                    session_adapter.set_username(login_payload["username"])
                    session_adapter.set_user_metadata(login_payload["metadata"])
                    session_adapter.set_auth_tokens(login_payload.get("access_token"), login_payload.get("refresh_token"))
                    session_adapter.set_profile(login_payload["profile"])
                    session_adapter.set_scroll_to_top(True)
                    load_user_data(login_payload["username"])
                    st.rerun()
                except APIClientError as error:
                    show_api_error(error)
                return

            if user_exists(normalized_username) and verify_password(normalized_username, password):
                session_adapter.set_logged_in(True)
                session_adapter.set_username(normalized_username)
                session_adapter.set_scroll_to_top(True)
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
                    beta_disclaimer_accepted_at=session_adapter.get_beta_disclaimer_accepted_at(
                        datetime.utcnow().isoformat(timespec="seconds")
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
    if session_adapter.pop_scroll_to_top():
        scroll_to_top()

    session_adapter.ensure_authenticated_defaults()


def ensure_subscription_or_stop(current_metadata):
    if has_active_subscription(session_adapter.get_username()):
        return

    show_subscription_required(session_adapter.get_username(), current_metadata.get("therapist_username"))
    st.divider()
    logout_button()
    st.stop()



def render_onboarding_or_stop():
    if session_adapter.get_profile().get("onboarding_completed", False):
        return

    st.markdown("**Benvenuto.** Prima di iniziare, aiutami a conoscerti meglio.")

    with st.form("onboarding"):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Come ti chiami?", value=session_adapter.get_profile().get("nome", ""))
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
            session_adapter.set_profile({
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
            })
            session_adapter.set_scroll_to_top(True)
            save_user_data(session_adapter.get_username())
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
            session_adapter.set_messages([])
            save_user_data(session_adapter.get_username())
            session_adapter.set_scroll_to_top(True)
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

    current_metadata = session_adapter.get_user_metadata()
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


def main():
    # ====================== LOGIN ======================
    if not session_adapter.is_logged_in():
        render_login_area()
        st.stop()

    render_authenticated_app()


if __name__ == "__main__":
    main()
