import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from api.app import app
from database import account_repository, filesystem_account_repository
from services.chat_service import ChatResponse


class PsyHelperAPITest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_account_dir = account_repository.USERS_DIR
        self.original_filesystem_dir = filesystem_account_repository.USERS_DIR
        account_repository.USERS_DIR = str(Path(self.tempdir.name) / "users")
        filesystem_account_repository.USERS_DIR = account_repository.USERS_DIR
        Path(account_repository.USERS_DIR).mkdir(parents=True, exist_ok=True)
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        account_repository.USERS_DIR = self.original_account_dir
        filesystem_account_repository.USERS_DIR = self.original_filesystem_dir
        self.tempdir.cleanup()

    def signup(self, username="giulia", password="secret"):
        response = self.client.post(
            "/auth/signup",
            json={
                "username": username,
                "password": password,
                "role": "client",
                "profile": {"nome": "Giulia"},
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_health_endpoint(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_signup_login_and_me(self):
        signup_payload = self.signup()
        self.assertEqual(signup_payload["username"], "giulia")
        self.assertTrue(signup_payload["authenticated"])

        login_response = self.client.post("/auth/login", json={"username": "giulia", "password": "secret"})
        self.assertEqual(login_response.status_code, 200, login_response.text)
        self.assertEqual(login_response.json()["profile"], {"nome": "Giulia"})

        me_response = self.client.get("/me", headers={"X-Username": "giulia"})
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertEqual(me_response.json()["metadata"]["role"], "client")

    def test_chat_endpoint_uses_chat_service(self):
        self.signup()
        with patch("api.routers.chat.groq_api_key", return_value="test-key"), patch(
            "api.routers.chat.get_chat_response", return_value=ChatResponse(content="Risposta API")
        ) as chat_mock:
            response = self.client.post(
                "/chat/messages",
                headers={"X-Username": "giulia"},
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
        create_response = self.client.post(
            "/clients/giulia/homework-assignments",
            headers={"X-Username": "giulia"},
            json={
                "template": "Nota per la seduta",
                "due_date": "2026-05-20",
                "assigned_by": "therapist_a",
                "prompt": "Scrivi una nota.",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        self.assertEqual(create_response.json()["assignment"]["template"], "Nota per la seduta")

        list_response = self.client.get("/clients/giulia/homework", headers={"X-Username": "giulia"})
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertEqual(len(list_response.json()["assignments"]), 1)
        self.assertEqual(list_response.json()["statuses"][0]["status"], "Da completare")

    def test_report_endpoints(self):
        self.signup()
        self.client.post(
            "/clients/giulia/mood-entries",
            headers={"X-Username": "giulia"},
            json={
                "data": "2026-05-18",
                "umore": "Ansioso",
                "umore_intensita": 7,
                "ansia": 6,
                "stress": 5,
                "trigger": "Lavoro",
            },
        )

        recap_response = self.client.get("/clients/giulia/weekly-recap", headers={"X-Username": "giulia"})
        self.assertEqual(recap_response.status_code, 200, recap_response.text)
        self.assertIn("Schede ultime 2 settimane", recap_response.json()["text"])

        report_response = self.client.get("/clients/giulia/clinical-report", headers={"X-Username": "giulia"})
        self.assertEqual(report_response.status_code, 200, report_response.text)
        self.assertEqual(report_response.json()["report"]["entries_count"], 1)


if __name__ == "__main__":
    unittest.main()
