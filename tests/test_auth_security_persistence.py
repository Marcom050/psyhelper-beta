import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from api.app import app
from database import account_repository, filesystem_account_repository
import database.audit_log as audit_log
import database.auth_security_repository as auth_security_repository


class AuthSecurityPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.users_dir = str(Path(self.tempdir.name) / "users")
        self.security_path = str(Path(self.tempdir.name) / "security.json")
        self.audit_path = str(Path(self.tempdir.name) / "audit.json")
        self.env = patch.dict(os.environ, {"SECRET_KEY": "x" * 40, "AUTH_SECURITY_STATE_PATH": self.security_path, "AUDIT_LOG_PATH": self.audit_path}, clear=False)
        self.env.start()
        self.original_account_dir = account_repository.USERS_DIR
        self.original_filesystem_dir = filesystem_account_repository.USERS_DIR
        account_repository.USERS_DIR = self.users_dir
        filesystem_account_repository.USERS_DIR = self.users_dir
        Path(self.users_dir).mkdir(parents=True, exist_ok=True)
        audit_log.AUDIT_LOG_PATH = self.audit_path
        auth_security_repository._SECURITY_PATH = self.security_path
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        account_repository.USERS_DIR = self.original_account_dir
        filesystem_account_repository.USERS_DIR = self.original_filesystem_dir
        self.env.stop()
        self.tempdir.cleanup()

    def _signup_and_login(self, username="alice"):
        self.client.post("/auth/signup", json={"username": username, "password": "secret", "role": "client", "profile": {"nome": "Alice"}})
        r = self.client.post("/auth/login", json={"username": username, "password": "secret"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_refresh_revocation_persistence(self):
        login = self._signup_and_login()
        refresh = login["refresh_token"]
        self.assertEqual(self.client.post("/auth/refresh", json={"refresh_token": refresh}).status_code, 200)
        self.assertEqual(self.client.post("/auth/refresh", json={"refresh_token": refresh}).status_code, 401)

    def test_refresh_reuse_detection(self):
        login = self._signup_and_login("bob")
        refresh = login["refresh_token"]
        self.client.post("/auth/refresh", json={"refresh_token": refresh})
        denied = self.client.post("/auth/refresh", json={"refresh_token": refresh})
        self.assertEqual(denied.status_code, 401)

    def test_lockout_persistence(self):
        self._signup_and_login("lockme")
        for _ in range(9):
            self.client.post("/auth/login", json={"username": "lockme", "password": "wrong"})
        denied = self.client.post("/auth/login", json={"username": "lockme", "password": "secret"})
        self.assertEqual(denied.status_code, 401)

    def test_multi_instance_consistency(self):
        login = self._signup_and_login("multi")
        refresh = login["refresh_token"]
        self.client.post("/auth/logout", json={"refresh_token": refresh})
        second_client = TestClient(app, raise_server_exceptions=False)
        denied = second_client.post("/auth/refresh", json={"refresh_token": refresh})
        self.assertEqual(denied.status_code, 401)

    def test_security_audit_generation(self):
        self._signup_and_login("audit")
        self.assertTrue(Path(self.audit_path).exists())

    def test_revoked_token_denied(self):
        login = self._signup_and_login("rev")
        refresh = login["refresh_token"]
        self.client.post("/auth/logout", json={"refresh_token": refresh})
        denied = self.client.post("/auth/refresh", json={"refresh_token": refresh})
        self.assertEqual(denied.status_code, 401)

    def test_logout_revokes_token(self):
        login = self._signup_and_login("logout")
        refresh = login["refresh_token"]
        self.assertEqual(self.client.post("/auth/logout", json={"refresh_token": refresh}).status_code, 200)
        self.assertEqual(self.client.post("/auth/refresh", json={"refresh_token": refresh}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
