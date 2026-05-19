from datetime import date
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from api.app import app
from database import account_repository, filesystem_account_repository
from database.filesystem_clinical_repository import FilesystemClinicalRepository
from services import analytics_service, auth_service
from scripts import backfill_clinical_records


def _bootstrap_users(tmp_path: Path):
    account_repository.USERS_DIR = str(tmp_path / "users")
    filesystem_account_repository.USERS_DIR = account_repository.USERS_DIR
    Path(account_repository.USERS_DIR).mkdir(parents=True, exist_ok=True)


def _set_clinical_paths(tmp_path: Path):
    from database import filesystem_clinical_repository as fcr

    fcr.CLINICAL_PATH = str(tmp_path / "clinical_records.json")
    fcr.SNAPSHOT_PATH = str(tmp_path / "analytics_snapshots.json")


def _headers(client: TestClient, username: str, password: str = "secret"):
    token = client.post("/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_therapist_and_client(client: TestClient, therapist="therapist_a", c="client_a"):
    assert client.post("/auth/signup", json={"username": therapist, "password": "secret", "role": "therapist", "subscription_status": "active", "commercial_terms_acceptance": {"accepted": True, "checkboxes": {"terms": True, "privacy": True, "billing": True}, "terms_version": "2026-01", "privacy_policy_version": "2026-01", "accepted_at": "2026-01-01T00:00:00Z", "policy_text": "commercial beta terms"}}).status_code == 200
    h = _headers(client, therapist)
    assert client.post(f"/therapists/me/clients", headers=h, json={"username": c, "password": "secret", "profile": {"nome": "Client"}}).status_code == 200
    return h


def test_tenant_required_for_clinical_record_query(tmp_path):
    _set_clinical_paths(tmp_path)
    repo = FilesystemClinicalRepository()
    try:
        repo.list_clinical_records(tenant_id=None)
        assert False
    except ValueError:
        assert True


def test_mood_entry_writes_clinical_record(tmp_path):
    _bootstrap_users(tmp_path)
    _set_clinical_paths(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    h = _create_therapist_and_client(client)
    res = client.post("/clients/client_a/mood-entries", headers=h, json={"data": "2026-05-19", "umore": "Ansia", "umore_intensita": 7, "ansia": 6, "stress": 5})
    assert res.status_code == 200
    records = FilesystemClinicalRepository().list_clinical_records(tenant_id="therapist_a", entity_type="mood_entry")
    assert len(records) == 1
    rec = records[0]
    assert rec["owner_username"] == "therapist_a" and rec["subject_username"] == "client_a"
    assert rec["lifecycle_status"] == "active" and rec["payload"]["ansia"] == 6


def test_homework_writes_clinical_record(tmp_path):
    _bootstrap_users(tmp_path); _set_clinical_paths(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    h = _create_therapist_and_client(client)
    assign = client.post("/clients/client_a/homework-assignments", headers=h, json={"template": "Nota per la seduta", "due_date": "2026-05-25", "assigned_by": "therapist_a", "prompt": "nota"}).json()["assignment"]
    assert FilesystemClinicalRepository().list_clinical_records(tenant_id="therapist_a", entity_type="homework_assignment")[0]["payload"]["id"] == assign["id"]
    sub = client.post("/homework-submissions", headers=h, json={"username": "client_a", "assignment_id": assign["id"], "template": "Nota per la seduta", "prompt": "nota", "answer": "ok"})
    assert sub.status_code == 200
    sub_records = FilesystemClinicalRepository().list_clinical_records(tenant_id="therapist_a", entity_type="homework_submission")
    assert sub_records and sub_records[0]["subject_username"] == "client_a"


def test_chat_writes_clinical_record(tmp_path):
    _bootstrap_users(tmp_path); _set_clinical_paths(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    h = _create_therapist_and_client(client)
    with patch("api.routers.chat.groq_api_key", return_value="k"), patch("api.routers.chat.get_chat_response") as g:
        g.return_value.content = "risposta"
        res = client.post("/chat/messages", headers=h, json={"username": "client_a", "user_input": "ciao", "profile": {}, "wellness": {}, "session_id": "s1"})
    assert res.status_code == 200
    rec = FilesystemClinicalRepository().list_clinical_records(tenant_id="therapist_a", entity_type="chat_message")[0]
    assert rec["payload"]["user_input"] == "ciao" and rec["metadata"]["source"] == "api"


def test_report_writes_clinical_record(tmp_path):
    _bootstrap_users(tmp_path); _set_clinical_paths(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    h = _create_therapist_and_client(client)
    res = client.get("/clients/client_a/clinical-report", headers=h)
    assert res.status_code == 200
    rec = FilesystemClinicalRepository().list_clinical_records(tenant_id="therapist_a", entity_type="report")[0]
    assert rec["lifecycle_status"] == "generated" and rec["subject_username"] == "client_a"


def test_analytics_snapshot_updates(tmp_path):
    _bootstrap_users(tmp_path); _set_clinical_paths(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    h = _create_therapist_and_client(client)
    client.post("/clients/client_a/mood-entries", headers=h, json={"data": "2026-05-19", "umore": "Ansia", "umore_intensita": 7, "ansia": 4, "stress": 3})
    snap = FilesystemClinicalRepository().get_analytics_snapshot(tenant_id="therapist_a", therapist_username="therapist_a", snapshot_date=date.today().isoformat())
    assert snap and snap["metrics"]["active_clients"] == 1


def test_analytics_prefers_snapshot():
    with patch("services.analytics_service.get_clinical_repository") as gcr, patch("services.analytics_service.auth_service.load_user_metadata", return_value={"tenant_id": "t1"}), patch("services.analytics_service.auth_service.resolve_tenant_id", return_value="t1"):
        gcr.return_value.get_analytics_snapshot.return_value = {"metrics": {"active_clients": 99}}
        out = analytics_service.therapist_overview("therapist_a")
        assert out["active_clients"] == 99


def test_archived_client_excluded_from_analytics():
    with patch("services.analytics_service.auth_service.get_clients_for_tenant", return_value=[{"username": "c1", "metadata": {"lifecycle_status": "archived"}}, {"username": "c2", "metadata": {}}]), patch("services.analytics_service.auth_service.load_account_bundle", return_value={"wellness": {"mood_entries": [], "homework_assignments": [], "homework_submissions": []}}):
        out = analytics_service.therapist_overview("t", allow_snapshot_fallback=False)
        assert out["active_clients"] == 1


def test_backfill_idempotent(tmp_path):
    _bootstrap_users(tmp_path); _set_clinical_paths(tmp_path)
    auth_service.create_user("therapist_a", "secret", role="therapist", subscription_status="active")
    auth_service.create_client_account("therapist_a", "client_a", "secret", "Client A")
    bundle = auth_service.load_account_bundle("client_a")
    bundle["wellness"]["mood_entries"] = [{"ansia": 3}, {"ansia": 4}]
    auth_service.save_account_bundle("client_a", bundle["profile"], bundle["messages"], bundle["wellness"])
    assert backfill_clinical_records.run("therapist_a", dry_run=True) == 2
    assert FilesystemClinicalRepository().list_clinical_records(tenant_id="therapist_a") == []
    assert backfill_clinical_records.run("therapist_a", dry_run=False) == 2
    first = FilesystemClinicalRepository().list_clinical_records(tenant_id="therapist_a", entity_type="mood_entry")
    assert len(first) == 2
    assert backfill_clinical_records.run("therapist_a", dry_run=False) == 2
    second = FilesystemClinicalRepository().list_clinical_records(tenant_id="therapist_a", entity_type="mood_entry")
    assert len(second) == 2


def test_analytics_legacy_fallback_when_snapshot_missing():
    clients = [
        {"username": "c_arch", "metadata": {"lifecycle_status": "archived"}},
        {"username": "c_susp", "metadata": {"lifecycle_status": "suspended"}},
        {"username": "c_active", "metadata": {}},
    ]

    def _bundle(username: str):
        return {"wellness": {"mood_entries": [], "homework_assignments": [], "homework_submissions": []}}

    with patch("services.analytics_service.get_clinical_repository") as gcr, \
        patch("services.analytics_service.auth_service.load_user_metadata", return_value={"tenant_id": "tenant_a"}), \
        patch("services.analytics_service.auth_service.resolve_tenant_id", return_value="tenant_a"), \
        patch("services.analytics_service.auth_service.get_clients_for_tenant", return_value=clients) as gclients, \
        patch("services.analytics_service.auth_service.load_account_bundle", side_effect=_bundle) as gbundle:
        gcr.return_value.get_analytics_snapshot.return_value = None
        out = analytics_service.therapist_overview("therapist_a")

    gclients.assert_called_once_with("therapist_a")
    loaded_users = [call.args[0] for call in gbundle.call_args_list]
    assert loaded_users == ["c_susp", "c_active"]
    assert out["active_clients"] == 2
