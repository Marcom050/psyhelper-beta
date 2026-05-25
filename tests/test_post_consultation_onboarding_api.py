import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from api.app import app
from database import account_repository, filesystem_account_repository


class PostConsultationOnboardingAPITest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_account_dir = account_repository.USERS_DIR
        self.original_filesystem_dir = filesystem_account_repository.USERS_DIR
        self.secret_patcher = patch.dict(os.environ, {"SECRET_KEY": "x" * 40}, clear=False)
        self.secret_patcher.start()
        account_repository.USERS_DIR = str(Path(self.tempdir.name) / "users")
        filesystem_account_repository.USERS_DIR = account_repository.USERS_DIR
        Path(account_repository.USERS_DIR).mkdir(parents=True, exist_ok=True)
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        account_repository.USERS_DIR = self.original_account_dir
        filesystem_account_repository.USERS_DIR = self.original_filesystem_dir
        self.secret_patcher.stop()
        self.tempdir.cleanup()

    def signup(self, username, password="secret", role="client", therapist_username=None, subscription_status="inactive"):
        return self.client.post("/auth/signup", json={"username": username, "password": password, "role": role, "therapist_username": therapist_username, "subscription_status": subscription_status, "profile": {"nome": username}})

    def auth_headers(self, username, password="secret"):
        token = self.client.post("/auth/login", json={"username": username, "password": password}).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def _setup_tenants(self):
        self.signup("th1", role="therapist", subscription_status="trialing")
        self.signup("th2", role="therapist", subscription_status="trialing")
        h1 = self.auth_headers("th1")
        h2 = self.auth_headers("th2")
        self.client.post("/therapists/me/clients", headers=h1, json={"username": "p1", "password": "pw"})
        self.client.post("/therapists/me/clients", headers=h2, json={"username": "p2", "password": "pw"})
        return h1, h2

    def test_onboarding_api_flow_and_rbac(self):
        h1, h2 = self._setup_tenants()
        p1 = self.auth_headers("p1", "pw")
        p2 = self.auth_headers("p2", "pw")

        created = self.client.post("/api/v1/post-consultation-onboarding", headers=h1, json={"patient_id": "p1"})
        self.assertEqual(created.status_code, 200)
        onboarding_id = created.json()["onboarding"]["id"]

        created_again = self.client.post("/api/v1/post-consultation-onboarding", headers=h1, json={"patient_id": "p1"})
        self.assertEqual(created_again.status_code, 200)
        self.assertEqual(created_again.json()["onboarding"]["id"], onboarding_id)

        self.assertEqual(self.client.get(f"/api/v1/post-consultation-onboarding/{onboarding_id}", headers=p1).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/v1/post-consultation-onboarding/{onboarding_id}/baseline", headers=p1, json={"sleep": 6}).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/v1/post-consultation-onboarding/{onboarding_id}/goals", headers=p1, json={"goals": ["x"], "track": "ansia"}).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/v1/post-consultation-onboarding/{onboarding_id}/diary", headers=p1, json={"entries": [{"day_index": 1}, {"day_index": 2}, {"day_index": 3}]}).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/v1/post-consultation-onboarding/{onboarding_id}/cbt-entry", headers=p1, json={"situation": "work"}).status_code, 200)
        done = self.client.patch(f"/api/v1/post-consultation-onboarding/{onboarding_id}/next-session-note", headers=p1, json={"must_discuss": "panic", "hard_to_say": "fear"})
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json()["status"], "completed")

        summary = self.client.get(f"/api/v1/post-consultation-onboarding/{onboarding_id}/summary", headers=h1)
        self.assertEqual(summary.status_code, 200)
        self.assertIn("non è diagnostico", summary.json()["summary"]["disclaimer"])

        self.assertEqual(self.client.post("/api/v1/post-consultation-onboarding", headers=p1, json={"patient_id": "p1"}).status_code, 401)
        self.assertEqual(self.client.get(f"/api/v1/post-consultation-onboarding/{onboarding_id}", headers=p2) .status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/post-consultation-onboarding/{onboarding_id}", headers=h2).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/post-consultation-onboarding", headers=h1, json={"patient_id": "p2"}).status_code, 401)

    def test_expired_status_is_reported(self):
        h1, _ = self._setup_tenants()
        created = self.client.post("/api/v1/post-consultation-onboarding", headers=h1, json={"patient_id": "p1"})
        onboarding_id = created.json()["onboarding"]["id"]
        from services import auth_service
        bundle = auth_service.load_account_bundle("p1")
        bundle["wellness"]["post_consultation_onboardings"][0]["expires_at"] = "2000-01-01T00:00:00+00:00"
        auth_service.save_account_bundle("p1", bundle["profile"], bundle["messages"], bundle["wellness"])
        response = self.client.get(f"/api/v1/post-consultation-onboarding/{onboarding_id}", headers=self.auth_headers("p1", "pw"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "expired")
