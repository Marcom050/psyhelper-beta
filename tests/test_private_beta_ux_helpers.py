from pathlib import Path
import importlib

import streamlit as st
from services.session_adapter import SessionAdapter


st.secrets = {}
app = importlib.import_module("psyhelper_streamlit")


def test_beta_disclaimer_lines_present():
    lines = app.beta_disclaimer_lines()
    assert len(lines) >= 4
    assert any("beta commerciale controllata" in line.lower() for line in lines)


def test_empty_state_messages_have_expected_keys():
    assert "crea nuovo paziente" in app.empty_state_message("clients").lower()
    assert "nessun dato disponibile" in app.empty_state_message("missing-key").lower()


def test_redact_sensitive_mapping_filters_secret_like_fields():
    payload = {
        "email": "therapist@test.local",
        "access_token": "abc",
        "refreshToken": "def",
        "password_hint": "none",
        "role": "therapist",
    }
    redacted = app.redact_sensitive_mapping(payload)
    assert "email" in redacted
    assert "role" in redacted
    assert "access_token" not in redacted
    assert "refreshToken" not in redacted
    assert "password_hint" not in redacted


def test_role_navigation_hides_admin_for_non_admin_roles():
    therapist_nav = app.role_nav_sections("therapist")
    client_nav = app.role_nav_sections("client")
    assert all("admin" not in item.lower() for item in therapist_nav)
    assert all("admin" not in item.lower() for item in client_nav)
    assert any("admin" in item.lower() for item in app.role_nav_sections("admin"))


def test_sanitize_session_metadata_hides_low_value_fields():
    payload = {"role": "therapist", "created_at": "2026-01-01", "internal_id": "abc", "email": "t@example.com"}
    sanitized = app.sanitize_session_metadata(payload)
    assert sanitized == {"role": "therapist", "email": "t@example.com"}


def test_clear_visible_chat_session_clears_messages_without_persistence_by_default(monkeypatch):
    app.session_adapter.set_messages([{"role": "user", "content": "ciao"}])
    app.session_adapter.set_selected_patient_username("cliente-demo")
    app.session_adapter._set("chat_messages", [{"role": "assistant", "content": "stale"}])
    app.session_adapter._set("chat_input_box", "bozza")

    called = {"saved": False}
    def fake_save(username):
        called["saved"] = True

    monkeypatch.setattr(app, "save_user_data", fake_save)
    app.clear_visible_chat_session(persist=False)

    assert app.session_adapter.get_messages() == []
    assert app.session_adapter.get_selected_patient_username() is None
    assert app.session_adapter._get("chat_messages") is None
    assert app.session_adapter._get("chat_input_box") is None
    assert called["saved"] is False


def test_clear_chat_button_label_is_italian_and_uses_shared_cleanup_path():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert 'if st.button("Pulisci chat corrente", use_container_width=True):' in source
    assert 'if st.button("Torna su", use_container_width=True):' in source
    assert 'if st.button("Esci", use_container_width=True):' in source
    assert "clear_visible_chat_session(persist=True)" in source
    assert "def reset_session_for_logout():" in source
    assert "clear_visible_chat_session(persist=True)" in source


def test_client_positioning_copy_mentions_personalization_and_therapist_control():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert "Ogni paziente è diverso" in source
    assert "senza imporre un approccio unico" in source
    assert "Il terapeuta mantiene sempre il controllo del percorso clinico." in source
    assert "non sostituisce valutazione clinica, relazione terapeutica o giudizio professionale" in source
    assert "Non fornisce diagnosi, non gestisce emergenze e non garantisce esiti clinici." in source


def test_runtime_session_adapter_exposes_clear_keys():
    adapter = SessionAdapter(session_state={})
    adapter._set("messages", [1])
    adapter._set("chat_input_box", "bozza")
    adapter.clear_keys(["messages", "chat_input_box"])
    assert adapter._get("messages") is None
    assert adapter._get("chat_input_box") is None


def test_clear_visible_chat_session_compatibility_without_clear_keys(monkeypatch):
    class LegacyAdapter:
        def __init__(self):
            self.storage = {"messages": [{"role": "user", "content": "ciao"}], "chat_input_box": "bozza"}
            self.selected = "cliente-demo"
            self.username = "tester"

        def set_messages(self, messages):
            self.storage["messages"] = messages

        def set_selected_patient_username(self, value):
            self.selected = value

        def _pop(self, key, default=None):
            return self.storage.pop(key, default)

        def get_username(self):
            return self.username

    legacy_adapter = LegacyAdapter()
    monkeypatch.setattr(app, "session_adapter", legacy_adapter)
    monkeypatch.setattr(app, "save_user_data", lambda username: None)
    app.clear_visible_chat_session(persist=True)
    assert legacy_adapter.storage.get("messages") is None
    assert legacy_adapter.selected is None
    assert "chat_input_box" not in legacy_adapter.storage


def test_diary_ui_no_cbt_alternative_response_field():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8").lower()
    assert "risposta alternativa cbt" not in source


def test_patient_delete_confirmation_copy_is_italian():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert "Elimina profilo" in source
    assert "Conferma eliminazione" in source
    assert "Vuoi davvero eliminare definitivamente il profilo di" in source
    assert "Questa azione è permanente e non può essere annullata." in source
    assert "Sì, elimina definitivamente" in source
    assert "Annulla" in source


def test_patient_delete_keys_and_pending_state_are_stable():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert 'key=f"delete_client_{client[\'username\']}"' in source
    assert 'key=f"confirm_delete_client_{pending_delete_username}"' in source
    assert 'key=f"cancel_delete_client_{pending_delete_username}"' in source
    assert '_set_pending_patient_delete(client["username"])' in source


def test_patient_selector_dialog_open_state_is_persistent():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert 'def _patient_selector_dialog_open() -> bool:' in source
    assert 'session_adapter._set("patient_selector_open", bool(is_open))' in source
    assert 'if _patient_selector_dialog_open():' in source


def test_post_free_consultation_onboarding_gate_exists():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert "def render_post_free_consultation_onboarding_or_stop():" in source
    assert "patient_onboarding_visibility_state(wellness, profile)" in source
    assert "find_active_post_consultation_onboarding(wellness)" in source
    assert "if visibility_state == \"completed\":" in source
    assert 'with st.form("post_free_consultation_onboarding"):' in source
    assert '"post_free_consultation_onboarding_completed": completed_steps_after == total_after' in source
    assert "render_post_free_consultation_onboarding_or_stop()" in source


def test_therapist_dashboard_starting_point_card_copy_exists():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert "Punto di partenza del percorso" in source
    assert "Avvia punto di partenza del percorso" in source
    assert "Apri punto di partenza" in source
    assert "Com’è andata questa settimana?" not in source
    assert "Sto valutando e voglio solo monitorare i progressi" not in source


def test_onboarding_helpers_status_progress_and_cta_labels():
    assert app.onboarding_status_label("active") == "Attivo"
    assert app.onboarding_status_label("completed") == "Completato"
    assert app.onboarding_status_label("expired") == "Scaduto"
    onboarding = {"steps": {name: {"completed": False} for name in ("baseline", "goals", "diary", "cbt", "next_session_note")}}
    onboarding["steps"]["baseline"]["completed"] = True
    assert app.onboarding_progress_label(onboarding) == "1/5 step completati"
    assert app.onboarding_primary_cta("active") == "Apri punto di partenza"
    assert app.onboarding_primary_cta("completed") == "Apri punto di partenza"
    assert app.onboarding_primary_cta("expired") == "Visualizza dati raccolti"


def test_find_existing_onboarding_does_not_depend_on_legacy_flag():
    wellness = {
        "post_consultation_onboardings": [
            {"id": "old", "status": "expired"},
            {"id": "active-one", "status": "active"},
        ]
    }
    selected = app.find_existing_post_consultation_onboarding(wellness)
    assert selected["id"] == "old"
    active = app.find_active_post_consultation_onboarding(wellness)
    assert active["id"] == "active-one"
    profile = {"post_free_consultation_onboarding_completed": True}
    assert app.should_show_patient_post_consultation_onboarding(wellness, profile) is True


def test_patient_visibility_state_active_even_without_free_consultation_flag():
    wellness = {"post_consultation_onboardings": [{"id": "a1", "status": "active"}]}
    state, item = app.patient_onboarding_visibility_state(wellness, profile={})
    assert state == "active"
    assert item["id"] == "a1"


def test_patient_visibility_completed_and_expired_hide_active_form():
    completed_wellness = {"post_consultation_onboardings": [{"id": "c1", "status": "completed"}]}
    expired_wellness = {"post_consultation_onboardings": [{"id": "e1", "status": "expired"}]}
    assert app.should_show_patient_post_consultation_onboarding(completed_wellness, {}) is False
    assert app.should_show_patient_post_consultation_onboarding(expired_wellness, {}) is False
    assert app.patient_onboarding_visibility_state(completed_wellness, {})[0] == "completed"
    assert app.patient_onboarding_visibility_state(expired_wellness, {})[0] == "expired"


def test_logout_cleanup_persists_and_prevents_chat_rehydration(monkeypatch):
    saved_messages = [{"role": "user", "content": "messaggio vecchio"}]
    app.session_adapter.set_username("cliente-test")
    app.session_adapter.set_logged_in(True)
    app.session_adapter.set_messages(saved_messages.copy())
    app.session_adapter._set("chat_messages", saved_messages.copy())
    app.session_adapter._set("current_chat", "stale")
    app.session_adapter.set_selected_patient_username("cliente-abc")

    persisted_bundle = {"messages": saved_messages.copy()}

    def fake_save(username):
        assert username == "cliente-test"
        persisted_bundle["messages"] = app.session_adapter.get_messages().copy()

    def fake_load(username):
        assert username == "cliente-test"
        app.session_adapter.set_messages(persisted_bundle["messages"].copy())

    monkeypatch.setattr(app, "save_user_data", fake_save)
    monkeypatch.setattr(app, "load_user_data", fake_load)

    app.reset_session_for_logout()
    assert app.session_adapter.get_messages() == []
    assert app.session_adapter.get_selected_patient_username() is None
    assert app.session_adapter._get("chat_messages") is None
    assert app.session_adapter._get("current_chat") is None
    assert persisted_bundle["messages"] == []

    app.session_adapter.set_username("cliente-test")
    app.load_user_data("cliente-test")
    assert app.session_adapter.get_messages() == []


def test_runtime_summary_state_uses_compatible_session_methods():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert "def get_runtime_state(key: str, default=None):" in source
    assert "def set_runtime_state(key: str, value) -> None:" in source
    assert "session_adapter._get(key, default)" in source
    assert "session_adapter._set(key, value)" in source
    assert "get_runtime_value(" not in source
    assert "set_runtime_value(" not in source



def test_progress_journey_copy_present_for_patient_and_therapist():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert "Il tuo percorso" in source
    assert "Percorso e ricadute" in source
    assert "Timeline del percorso" in source
    assert "Non ci sono ancora eventi sufficienti per costruire una timeline del percorso." in source
    assert "Segnali di miglioramento" in source
    assert "Momenti di difficoltà" in source
    assert "Da portare in seduta" in source
    assert "journey = build_progress_journey_summary(selected_wellness)" in source


def test_initial_patient_onboarding_collects_baseline_without_monitoring_overwrite():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert "Prima di iniziare, raccogliamo un piccolo punto di partenza" in source
    assert "Come ti senti in questo momento?" in source
    assert "Quanta ansia senti in questo momento?" in source
    assert "Quanto stress senti in questo momento?" in source
    assert "Quanto ti senti motivato a iniziare questo percorso?" in source
    assert '"initial_baseline": {' in source
    assert '"source": "initial_patient_onboarding"' in source
    assert '"ansia": ansia' in source
    assert '"stress": stress' in source
    assert '"motivazione": motivazione' in source
    assert 'mood_entries' not in source[source.index('def render_onboarding_or_stop():'):source.index('@st.dialog("🧭 Da dove vuoi iniziare?")')]


def test_patient_selector_uses_isolated_open_key_and_closes_on_selection():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert 'session_adapter._get("patient_selector_open", False)' in source
    assert 'session_adapter._set("patient_selector_open", bool(is_open))' in source
    assert 'session_adapter._set("patient_selector_dialog_open", bool(is_open))' not in source
    select_block_start = source.index('key=f"select_patient_dialog_{client[\'username\']}"')
    select_block = source[select_block_start:select_block_start + 250]
    assert '_set_patient_selector_dialog_open(False)' in select_block
