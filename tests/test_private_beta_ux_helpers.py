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
