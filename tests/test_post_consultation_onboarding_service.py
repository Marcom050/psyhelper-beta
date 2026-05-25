from datetime import UTC, datetime, timedelta

from services import auth_service
from services.post_consultation_onboarding_service import activate_onboarding, build_post_consultation_summary, get_onboarding, update_step
from api.exceptions import AuthenticationError


def _mk_user(username, role, therapist_username=None):
    auth_service.create_user(username, "password123", role=role, therapist_username=therapist_username, subscription_status="active")


def test_full_flow_and_completion(tmp_path, monkeypatch):
    monkeypatch.setenv("PSYHELPER_DATA_DIR", str(tmp_path))
    _mk_user("ther1", "therapist")
    _mk_user("pat1", "client", "ther1")
    onboarding = activate_onboarding(therapist_id="ther1", patient_id="pat1", tenant_id="tenant-a")
    assert onboarding["status"] == "active"
    oid = onboarding["id"]
    update_step("pat1", oid, "baseline", {"mood": 5})
    update_step("pat1", oid, "goals", ["goal1", "goal2"])
    update_step("pat1", oid, "diary_entries", [{"day_index":1,"emotion":"ansia","intensity":6,"event":"lavoro","automatic_thought":"non ce la faccio","behavior":"evito"}] * 3)
    update_step("pat1", oid, "cbt_entry", {"situation":"riunione"})
    updated = update_step("pat1", oid, "next_session_note", {"must_discuss":"gestire ansia","hard_to_say":"mi sento in colpa"})
    assert updated["status"] == "completed"
    assert updated["completed_steps"] == 5
    summary = build_post_consultation_summary("pat1", "ther1", oid)
    assert "non è una diagnosi" in summary["disclaimer"]
    assert summary["must_discuss"] == "gestire ansia"


def test_expired_status(tmp_path, monkeypatch):
    monkeypatch.setenv("PSYHELPER_DATA_DIR", str(tmp_path))
    _mk_user("ther1", "therapist")
    _mk_user("pat1", "client", "ther1")
    past = datetime.now(UTC) - timedelta(days=5)
    onboarding = activate_onboarding(therapist_id="ther1", patient_id="pat1", tenant_id="tenant-a", now=past)
    got = get_onboarding("pat1", onboarding["id"])
    assert got["status"] == "expired"


def test_tenant_access_guards(tmp_path, monkeypatch):
    monkeypatch.setenv("PSYHELPER_DATA_DIR", str(tmp_path))
    _mk_user("ther1", "therapist")
    _mk_user("ther2", "therapist")
    _mk_user("pat1", "client", "ther1")
    onboarding = activate_onboarding(therapist_id="ther1", patient_id="pat1", tenant_id="tenant-a")
    with __import__('pytest').raises(AuthenticationError):
        build_post_consultation_summary("pat1", "ther2", onboarding["id"])
