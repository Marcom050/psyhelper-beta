import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from api.app import app
from api.security import _encode_hs256
from database import account_repository, filesystem_account_repository
from services.chat_service import ChatResponse


class PsyHelperAPITest(unittest.TestCase):
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

    def signup(self, username="giulia", password="secret", role="client", therapist_username=None, subscription_status="inactive"):
        response = self.client.post(
            "/auth/signup",
            json={
                "username": username,
                "password": password,
                "role": role,
                "therapist_username": therapist_username,
                "subscription_status": subscription_status,
                "profile": {"nome": username.title()},
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def login(self, username="giulia", password="secret"):
        response = self.client.post("/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def auth_headers(self, username="giulia", password="secret"):
        token = self.login(username, password)["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_health_endpoint(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_signup_login_refresh_and_me_use_jwt(self):
        signup_payload = self.signup()
        self.assertEqual(signup_payload["username"], "giulia")
        self.assertTrue(signup_payload["authenticated"])

        login_payload = self.login()
        self.assertEqual(login_payload["profile"], {"nome": "Giulia"})
        self.assertEqual(login_payload["token_type"], "bearer")
        self.assertTrue(login_payload["access_token"])
        self.assertTrue(login_payload["refresh_token"])

        refresh_response = self.client.post("/auth/refresh", json={"refresh_token": login_payload["refresh_token"]})
        self.assertEqual(refresh_response.status_code, 200, refresh_response.text)
        self.assertTrue(refresh_response.json()["access_token"])

        me_response = self.client.get("/me", headers={"Authorization": f"Bearer {login_payload['access_token']}"})
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertEqual(me_response.json()["metadata"]["role"], "client")

    def test_invalid_and_expired_tokens_are_denied(self):
        self.signup()
        invalid_response = self.client.get("/me", headers={"Authorization": "Bearer invalid.token.value"})
        self.assertEqual(invalid_response.status_code, 401)

        expired = _encode_hs256(
            {"sub": "giulia", "typ": "access", "iat": 1, "nbf": 1, "exp": 1, "iss": "psyhelper-beta"},
            "x" * 40,
        )
        expired_response = self.client.get("/me", headers={"Authorization": f"Bearer {expired}"})
        self.assertEqual(expired_response.status_code, 401)

    def test_chat_endpoint_uses_chat_service(self):
        self.signup()
        with patch("api.routers.chat.groq_api_key", return_value="test-key"), patch(
            "api.routers.chat.get_chat_response", return_value=ChatResponse(content="Risposta API")
        ) as chat_mock:
            response = self.client.post(
                "/chat/messages",
                headers=self.auth_headers(),
                json={
                    "username": "giulia",
                    "user_input": "Sono in ansia",
                    "profile": {"nome": "Giulia"},
                    "wellness": {"mood_entries": []},
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"username": "giulia", "content": "Risposta API"})
        chat_mock.assert_called_once()
        self.assertEqual(chat_mock.call_args.args[0].user_input, "Sono in ansia")

    def test_homework_endpoint_creates_and_lists_assignment(self):
        self.signup()
        headers = self.auth_headers()
        create_response = self.client.post(
            "/clients/giulia/homework-assignments",
            headers=headers,
            json={
                "template": "Nota per la seduta",
                "due_date": "2026-05-20",
                "assigned_by": "therapist_a",
                "prompt": "Scrivi una nota.",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        self.assertEqual(create_response.json()["assignment"]["template"], "Nota per la seduta")

        list_response = self.client.get("/clients/giulia/homework", headers=headers)
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertEqual(len(list_response.json()["assignments"]), 1)
        self.assertEqual(list_response.json()["statuses"][0]["status"], "Da completare")

        submission_response = self.client.post(
            "/homework-submissions",
            headers=headers,
            json={
                "username": "giulia",
                "assignment_id": create_response.json()["assignment"]["id"],
                "template": "Nota per la seduta",
                "prompt": "Scrivi una nota.",
                "answer": "Porto questa nota in seduta.",
            },
        )
        self.assertEqual(submission_response.status_code, 200, submission_response.text)
        self.assertEqual(submission_response.json()["submission"]["template"], "Nota per la seduta")

        completed_response = self.client.get("/clients/giulia/homework", headers=headers)
        self.assertEqual(completed_response.status_code, 200, completed_response.text)
        self.assertEqual(len(completed_response.json()["submissions"]), 1)
        self.assertEqual(completed_response.json()["statuses"][0]["status"], "Completato")

    def test_report_endpoints(self):
        self.signup()
        headers = self.auth_headers()
        self.client.post(
            "/clients/giulia/mood-entries",
            headers=headers,
            json={
                "data": "2026-05-18",
                "umore": "Ansioso",
                "umore_intensita": 7,
                "ansia": 6,
                "stress": 5,
                "trigger": "Lavoro",
            },
        )

        recap_response = self.client.get("/clients/giulia/weekly-recap", headers=headers)
        self.assertEqual(recap_response.status_code, 200, recap_response.text)
        self.assertIn("Schede ultime 2 settimane", recap_response.json()["text"])

        report_response = self.client.get("/clients/giulia/clinical-report", headers=headers)
        self.assertEqual(report_response.status_code, 200, report_response.text)
        self.assertEqual(report_response.json()["report"]["entries_count"], 1)

    def test_therapist_access_and_ownership_enforcement(self):
        self.signup("thera", role="therapist", subscription_status="trialing")
        self.signup("otherthera", role="therapist", subscription_status="trialing")
        thera_headers = self.auth_headers("thera")
        other_headers = self.auth_headers("otherthera")

        create_response = self.client.post(
            "/therapists/me/clients",
            headers=thera_headers,
            json={"username": "clienta", "password": "clientpass", "profile": {"nome": "Client A"}},
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        self.assertEqual(create_response.json()["metadata"]["therapist_username"], "thera")

        list_response = self.client.get("/therapists/me/clients", headers=thera_headers)
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertEqual(list_response.json()["clients"][0]["username"], "clienta")

        own_response = self.client.get("/therapists/me/clients/clienta", headers=thera_headers)
        self.assertEqual(own_response.status_code, 200, own_response.text)
        self.assertIn("wellness", own_response.json())

        foreign_response = self.client.get("/therapists/me/clients/clienta", headers=other_headers)
        self.assertEqual(foreign_response.status_code, 401)

        client_headers = self.auth_headers("clienta", "clientpass")
        other_client_response = self.client.get("/clients/thera/wellness", headers=client_headers)
        self.assertEqual(other_client_response.status_code, 401)
        therapist_endpoint_response = self.client.get("/therapists/me/clients/clienta", headers=client_headers)
        self.assertEqual(therapist_endpoint_response.status_code, 401)

    def test_therapist_can_delete_owned_client_and_cross_tenant_is_denied(self):
        self.signup("thera", role="therapist", subscription_status="trialing")
        self.signup("otherthera", role="therapist", subscription_status="trialing")
        thera_headers = self.auth_headers("thera")
        other_headers = self.auth_headers("otherthera")
        self.client.post(
            "/therapists/me/clients",
            headers=thera_headers,
            json={"username": "clientdel", "password": "clientpass", "profile": {"nome": "Client Del"}},
        )

        denied = self.client.delete("/therapists/me/clients/clientdel", headers=other_headers)
        self.assertEqual(denied.status_code, 401)

        deleted = self.client.delete("/therapists/me/clients/clientdel", headers=thera_headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json()["deleted"], True)

        list_response = self.client.get("/therapists/me/clients", headers=thera_headers)
        usernames = [item["username"] for item in list_response.json()["clients"]]
        self.assertNotIn("clientdel", usernames)

    def test_client_role_cannot_delete_patient(self):
        self.signup("thera", role="therapist", subscription_status="trialing")
        therapist_headers = self.auth_headers("thera")
        self.client.post(
            "/therapists/me/clients",
            headers=therapist_headers,
            json={"username": "clientx", "password": "clientpass", "profile": {"nome": "Client X"}},
        )
        client_headers = self.auth_headers("clientx", "clientpass")
        denied = self.client.delete("/therapists/me/clients/clientx", headers=client_headers)
        self.assertEqual(denied.status_code, 401)

    def test_legacy_header_auth_requires_explicit_flag(self):
        self.signup()
        denied = self.client.get("/me", headers={"X-Username": "giulia"})
        self.assertEqual(denied.status_code, 401)
        with patch.dict(os.environ, {"USE_LEGACY_HEADER_AUTH": "true"}, clear=False):
            allowed = self.client.get("/me", headers={"X-Username": "giulia"})
        self.assertEqual(allowed.status_code, 200, allowed.text)


if __name__ == "__main__":
    unittest.main()
