import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from api.app import app
from api.security import create_access_token
from database import account_repository, config, filesystem_account_repository
from database.postgres.account_repository_pg import PostgresAccountRepository
from database.tenant_metadata import normalize_tenant_metadata, resolve_tenant_id, resolve_tenant_owner
from services import auth_service, subscription_service


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.queries.append((sql, params))

    def fetchone(self):
        if self.rows:
            return self.rows.pop(0)
        return None

    def fetchall(self):
        if self.rows:
            rows = self.rows
            self.rows = []
            return rows
        return []


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True


class ConnectionContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


class TenantArchitectureTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_account_dir = account_repository.USERS_DIR
        self.original_filesystem_dir = filesystem_account_repository.USERS_DIR
        account_repository.USERS_DIR = str(Path(self.tempdir.name) / "users")
        filesystem_account_repository.USERS_DIR = account_repository.USERS_DIR
        Path(account_repository.USERS_DIR).mkdir(parents=True, exist_ok=True)
        config.USE_POSTGRESQL = False
        config.USE_FILESYSTEM_FALLBACK = True

    def tearDown(self):
        account_repository.USERS_DIR = self.original_account_dir
        filesystem_account_repository.USERS_DIR = self.original_filesystem_dir
        config.USE_POSTGRESQL = False
        config.USE_FILESYSTEM_FALLBACK = True
        self.tempdir.cleanup()

    def test_tenant_normalization_and_ownership(self):
        therapist = normalize_tenant_metadata({"role": "therapist", "subscription_status": "trialing"}, username="Dr Rossi")
        client = normalize_tenant_metadata({"role": "client", "therapist_username": "Dr Rossi"}, username="Client A")

        self.assertEqual(therapist["tenant_id"], "dr_rossi")
        self.assertEqual(therapist["tenant_role"], "owner")
        self.assertEqual(client["tenant_id"], "dr_rossi")
        self.assertEqual(client["tenant_role"], "member")
        self.assertEqual(resolve_tenant_id(client, "client_a"), "dr_rossi")
        self.assertEqual(resolve_tenant_owner(client, "client_a"), "dr_rossi")

    def test_tenant_safe_queries_and_subscription_inheritance(self):
        auth_service.create_user("therapist_a", "pass", role="therapist", subscription_status="active")
        auth_service.create_client_account("therapist_a", "client_a", "pass", "Client A")
        auth_service.create_user("therapist_b", "pass", role="therapist", subscription_status="active")
        auth_service.create_client_account("therapist_b", "client_b", "pass", "Client B")

        clients = auth_service.get_clients_for_tenant("therapist_a")
        self.assertEqual([client["username"] for client in clients], ["client_a"])
        self.assertTrue(auth_service.is_same_tenant("therapist_a", "client_a"))
        self.assertFalse(auth_service.is_same_tenant("therapist_a", "client_b"))
        subscription = subscription_service.subscription_state_for("client_a")
        self.assertTrue(subscription["inherited"])
        self.assertEqual(subscription["owner_username"], "therapist_a")
        self.assertEqual(subscription["subscription_status"], "active")

    def test_therapist_dashboard_and_snapshot_endpoints(self):
        auth_service.create_user("therapist_a", "pass", role="therapist", subscription_status="active")
        auth_service.create_client_account("therapist_a", "client_a", "pass", "Client A")
        bundle = auth_service.load_account_bundle("client_a")
        bundle["wellness"]["mood_entries"].append({"date": "2026-05-19", "mood": 7})
        bundle["wellness"]["homework_assignments"].append({"id": "hw1", "template": "Nota"})
        auth_service.save_account_bundle("client_a", bundle["profile"], bundle["messages"], bundle["wellness"])

        client = TestClient(app, raise_server_exceptions=False)
        headers = {"Authorization": f"Bearer {create_access_token('therapist_a')}"}
        dashboard = client.get("/therapists/me/dashboard", headers=headers)
        snapshot = client.get("/therapists/me/clients/client_a/snapshot", headers=headers)

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["tenant"]["tenant_id"], "therapist_a")
        self.assertEqual(dashboard.json()["stats"]["total_clients"], 1)
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json()["wellness_summary"]["mood_entries_count"], 1)
        self.assertEqual(snapshot.json()["homework_summary"]["open_assignments"], 1)

    def test_postgres_password_fallback_sync_and_disable_mode(self):
        filesystem_account_repository.create_user("client_a", "secret")
        config.USE_FILESYSTEM_FALLBACK = True
        password_cursor = FakeCursor(rows=[None])
        save_cursor = FakeCursor()
        cursors = [password_cursor, save_cursor]

        def fake_connection():
            return ConnectionContext(FakeConnection(cursors.pop(0)))

        with mock.patch("database.postgres.account_repository_pg.initialize_schema"), \
             mock.patch("database.postgres.account_repository_pg.connection", side_effect=fake_connection):
            repository = PostgresAccountRepository()
            self.assertTrue(repository.verify_password("client_a", "secret"))

        self.assertTrue(save_cursor.queries)
        config.USE_FILESYSTEM_FALLBACK = False
        missing_cursor = FakeCursor(rows=[None])
        with mock.patch("database.postgres.account_repository_pg.initialize_schema"), \
             mock.patch("database.postgres.account_repository_pg.connection", return_value=ConnectionContext(FakeConnection(missing_cursor))):
            repository = PostgresAccountRepository()
            self.assertFalse(repository.verify_password("client_a", "secret"))
