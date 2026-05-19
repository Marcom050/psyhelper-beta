from pathlib import Path
import importlib

import streamlit as st


st.secrets = {}
app = importlib.import_module("psyhelper_streamlit")


def test_beta_disclaimer_lines_present():
    lines = app.beta_disclaimer_lines()
    assert len(lines) >= 4
    assert any("private beta" in line.lower() for line in lines)


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
    assert 'if st.button("Pulisci chat corrente"):' in source
    assert "clear_visible_chat_session(persist=True)" in source


def test_diary_ui_no_cbt_alternative_response_field():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8").lower()
    assert "risposta alternativa cbt" not in source
