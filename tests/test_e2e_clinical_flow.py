from datetime import date
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from api.app import app
from database import account_repository, filesystem_account_repository
from database.filesystem_clinical_repository import FilesystemClinicalRepository


def _setup(tmp_path: Path):
    account_repository.USERS_DIR = str(tmp_path / "users")
    filesystem_account_repository.USERS_DIR = account_repository.USERS_DIR
    Path(account_repository.USERS_DIR).mkdir(parents=True, exist_ok=True)
    from database import filesystem_clinical_repository as fcr

    fcr.CLINICAL_PATH = str(tmp_path / "clinical_records.json")
    fcr.SNAPSHOT_PATH = str(tmp_path / "analytics_snapshots.json")


def _login(client, u, p="secret"):
    return {"Authorization": f"Bearer {client.post('/auth/login', json={'username': u, 'password': p}).json()['access_token']}"}


def test_e2e_clinical_flow(tmp_path):
    _setup(tmp_path)
    c = TestClient(app, raise_server_exceptions=False)

    assert c.post("/auth/signup", json={"username": "thera", "password": "secret", "role": "therapist", "subscription_status": "active", "commercial_terms_acceptance": {"accepted": True, "checkboxes": {"terms": True, "privacy": True, "billing": True}, "terms_version": "2026-01", "privacy_policy_version": "2026-01", "accepted_at": "2026-01-01T00:00:00Z", "policy_text": "commercial beta terms"}}).status_code == 200
    th = _login(c, "thera")
    assert c.post("/therapists/me/clients", headers=th, json={"username": "client1", "password": "secret", "profile": {"nome": "C1"}}).status_code == 200

    assert c.post("/clients/client1/mood-entries", headers=th, json={"data": "2026-05-19", "umore": "Ansioso", "umore_intensita": 8, "ansia": 7, "stress": 6}).status_code == 200
    hw = c.post("/clients/client1/homework-assignments", headers=th, json={"template": "Nota per la seduta", "due_date": "2026-05-30", "assigned_by": "thera", "prompt": "nota"}).json()["assignment"]
    assert c.post("/homework-submissions", headers=th, json={"username": "client1", "assignment_id": hw["id"], "template": "Nota per la seduta", "prompt": "nota", "answer": "fatto"}).status_code == 200
    with patch("api.routers.chat.groq_api_key", return_value="k"), patch("api.routers.chat.get_chat_response") as g:
        g.return_value.content = "ok"
        assert c.post("/chat/messages", headers=th, json={"username": "client1", "user_input": "ciao", "profile": {}, "wellness": {}, "session_id": "s-e2e"}).status_code == 200
    assert c.get("/clients/client1/clinical-report", headers=th).status_code == 200

    repo = FilesystemClinicalRepository()
    assert repo.get_analytics_snapshot(tenant_id="thera", therapist_username="thera", snapshot_date=date.today().isoformat()) is not None
    all_types = {r["entity_type"] for r in repo.list_clinical_records(tenant_id="thera")}
    assert {"mood_entry", "homework_assignment", "homework_submission", "chat_message", "report"}.issubset(all_types)

    assert c.post("/auth/signup", json={"username": "other", "password": "secret", "role": "therapist", "subscription_status": "active", "commercial_terms_acceptance": {"accepted": True, "checkboxes": {"terms": True, "privacy": True, "billing": True}, "terms_version": "2026-01", "privacy_policy_version": "2026-01", "accepted_at": "2026-01-01T00:00:00Z", "policy_text": "commercial beta terms"}}).status_code == 200
    oh = _login(c, "other")
    denied = c.get("/clients/client1/clinical-report", headers=oh)
    assert denied.status_code == 401

