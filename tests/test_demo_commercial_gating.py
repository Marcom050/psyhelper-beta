from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from services import subscription_access, subscription_service


class MemoryAccounts:
    def __init__(self, records):
        self.records = records
        self.deleted = []

    def load_user_metadata(self, username):
        return dict(self.records[username])

    def delete_user_account(self, username):
        self.deleted.append(username)


def expired_therapist(**overrides):
    metadata = {
        "role": "therapist",
        "created_at": (datetime.now(UTC) - timedelta(days=60)).isoformat(),
        "subscription_status": "trialing",
        "billing_status": "past_due",
        "subscription_expires_at": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
    }
    metadata.update(overrides)
    return metadata


def test_expired_and_past_due_therapist_has_demo_access(monkeypatch):
    demo_settings = SimpleNamespace(commercial_gating_enabled=False)
    monkeypatch.setattr(subscription_service, "SETTINGS", demo_settings)
    monkeypatch.setattr(subscription_access, "SETTINGS", demo_settings)
    repository = MemoryAccounts({"therapist": expired_therapist()})
    assert subscription_service.is_subscription_active_for("therapist", {"active"}, repository)
    assert subscription_access.tenant_access_state("therapist", repository)["can_write"] is True
    assert repository.deleted == []


def test_linked_patient_inherits_unlimited_demo_access(monkeypatch):
    demo_settings = SimpleNamespace(commercial_gating_enabled=False)
    monkeypatch.setattr(subscription_service, "SETTINGS", demo_settings)
    monkeypatch.setattr(subscription_access, "SETTINGS", demo_settings)
    repository = MemoryAccounts({
        "therapist": expired_therapist(),
        "patient": {"role": "client", "therapist_username": "therapist", "tenant_id": "therapist"},
    })
    assert subscription_service.is_subscription_active_for("patient", {"active"}, repository)
    assert subscription_access.tenant_access_state("patient", repository)["can_read"] is True


def test_normal_ui_has_no_commercial_dashboard_copy():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    dashboard = source[source.index("def show_therapist_dashboard"):source.index("def reset_session_for_logout")]
    assert "trial_days_remaining" not in dashboard
    assert "Dashboard terapeuta · Private Beta" not in source
    assert 'st.info(DEMO_NOTICE)' in source
    assert "if SHOW_DEBUG_UI:\n    render_analytics_banner()" in source


def test_manual_patient_deletion_is_secondary_and_confirmed():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert 'with st.expander(f"Gestione profilo' in source
    assert "Questa azione è permanente e non può essere annullata." in source
    assert "Sì, elimina definitivamente" in source
