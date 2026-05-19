import unittest
from unittest.mock import Mock

import requests

from clients.api_client import APIClientConfig, PsyHelperAPIClient
from clients.exceptions import (
    APIHTTPError,
    APINotFoundError,
    APIResponseValidationError,
    APITimeoutError,
    APIUnauthorizedError,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


class PsyHelperAPIClientTest(unittest.TestCase):
    def make_client(self, response=None, side_effect=None):
        session = Mock()
        session.request = Mock(return_value=response, side_effect=side_effect)
        config = APIClientConfig(base_url="http://api.local", timeout_seconds=2.5, use_http_api=True)
        return PsyHelperAPIClient(config, session=session), session

    def test_health_success_path(self):
        client, session = self.make_client(FakeResponse(payload={"status": "ok"}))

        self.assertEqual(client.health(), {"status": "ok"})
        session.request.assert_called_once_with(
            "GET",
            "http://api.local/health",
            json=None,
            headers={"Accept": "application/json"},
            timeout=2.5,
        )

    def test_api_client_success_path_and_parsing_response(self):
        client, session = self.make_client(
            FakeResponse(
                payload={
                    "username": "giulia",
                    "authenticated": True,
                    "metadata": {"role": "client"},
                    "profile": {"nome": "Giulia"},
                }
            )
        )

        payload = client.login("giulia", "secret")

        self.assertEqual(payload["username"], "giulia")
        self.assertEqual(payload["metadata"], {"role": "client"})
        session.request.assert_called_once_with(
            "POST",
            "http://api.local/auth/login",
            json={"username": "giulia", "password": "secret"},
            headers={"Accept": "application/json"},
            timeout=2.5,
        )

    def test_get_me_sends_x_username_header(self):
        client, session = self.make_client(
            FakeResponse(payload={"username": "giulia", "metadata": {"role": "client"}, "profile": {}})
        )

        self.assertEqual(client.me("giulia")["username"], "giulia")

        self.assertEqual(session.request.call_args.kwargs["headers"]["X-Username"], "giulia")

    def test_chat_message_success_flow_and_response_parsing(self):
        payload = {"username": "giulia", "content": "Risposta API"}
        client, session = self.make_client(FakeResponse(payload=payload))

        response = client.chat_message(
            "giulia",
            "Sono in ansia",
            {"nome": "Giulia"},
            {"mood_entries": []},
        )

        self.assertEqual(response, payload)
        session.request.assert_called_once_with(
            "POST",
            "http://api.local/chat/messages",
            json={
                "username": "giulia",
                "user_input": "Sono in ansia",
                "profile": {"nome": "Giulia"},
                "wellness": {"mood_entries": []},
            },
            headers={"Accept": "application/json", "X-Username": "giulia"},
            timeout=2.5,
        )

    def test_chat_message_parsing_rejects_invalid_response(self):
        client, _session = self.make_client(FakeResponse(payload={"username": "giulia"}))

        with self.assertRaises(APIResponseValidationError):
            client.chat_message("giulia", "Ciao", {}, {})

    def test_get_wellness_returns_compatible_wellness_shape(self):
        wellness = {"mood_entries": [{"data": "2026-05-18", "ansia": 4}], "metadata": {}}
        client, _session = self.make_client(FakeResponse(payload={"username": "giulia", "wellness": wellness}))

        self.assertEqual(client.get_wellness("giulia"), wellness)

    def test_create_mood_entry_parses_response(self):
        wellness = {"mood_entries": [{"data": "2026-05-18", "ansia": 4}]}
        client, session = self.make_client(
            FakeResponse(
                payload={
                    "username": "giulia",
                    "mood_entry": {"data": "2026-05-18", "ansia": 4},
                    "wellness": wellness,
                }
            )
        )

        response = client.create_mood_entry("giulia", {"data": "2026-05-18", "ansia": 4})

        self.assertEqual(response["wellness"], wellness)
        self.assertEqual(session.request.call_args.args[:2], ("POST", "http://api.local/clients/giulia/mood-entries"))

    def test_http_error_handling_401_404_and_validation_error(self):
        client_401, _session_401 = self.make_client(
            FakeResponse(status_code=401, payload={"error": {"message": "Invalid credentials"}})
        )
        with self.assertRaises(APIUnauthorizedError):
            client_401.login("giulia", "wrong")

        client_404, _session_404 = self.make_client(FakeResponse(status_code=404, payload={"error": {"message": "Missing"}}))
        with self.assertRaises(APINotFoundError):
            client_404.get_wellness("giulia")

        client_422, _session_422 = self.make_client(
            FakeResponse(status_code=422, payload={"error": {"message": "Invalid body"}})
        )
        with self.assertRaises(APIHTTPError):
            client_422.create_mood_entry("giulia", {})

        client_403, _session_403 = self.make_client(
            FakeResponse(status_code=403, payload={"error": {"message": "Forbidden"}})
        )
        with self.assertRaises(APIUnauthorizedError):
            client_403.chat_message("giulia", "Ciao", {}, {})


    def test_bearer_token_header_and_refresh_retry(self):
        session = Mock()
        session.request = Mock(
            side_effect=[
                FakeResponse(status_code=401, payload={"error": {"message": "Expired"}}),
                FakeResponse(payload={"access_token": "new-access", "token_type": "bearer"}),
                FakeResponse(payload={"username": "giulia", "metadata": {"role": "client"}, "profile": {}}),
            ]
        )
        config = APIClientConfig(base_url="http://api.local", timeout_seconds=2.5, use_http_api=True)
        client = PsyHelperAPIClient(config, session=session, access_token="old-access", refresh_token="refresh-token")

        payload = client.me("giulia")

        self.assertEqual(payload["username"], "giulia")
        self.assertEqual(client.access_token, "new-access")
        first_headers = session.request.call_args_list[0].kwargs["headers"]
        refresh_call = session.request.call_args_list[1]
        retry_headers = session.request.call_args_list[2].kwargs["headers"]
        self.assertEqual(first_headers["Authorization"], "Bearer old-access")
        self.assertEqual(refresh_call.args[:2], ("POST", "http://api.local/auth/refresh"))
        self.assertEqual(retry_headers["Authorization"], "Bearer new-access")

    def test_login_stores_tokens_for_later_requests(self):
        client, session = self.make_client(
            FakeResponse(
                payload={
                    "username": "giulia",
                    "authenticated": True,
                    "access_token": "access",
                    "refresh_token": "refresh",
                    "token_type": "bearer",
                    "metadata": {"role": "client"},
                    "profile": {},
                }
            )
        )

        client.login("giulia", "secret")

        self.assertEqual(client.access_token, "access")
        self.assertEqual(client.refresh_token, "refresh")


    def test_therapist_api_client_methods_use_bearer_token(self):
        client, session = self.make_client(FakeResponse(payload={"clients": []}))
        client.set_auth_tokens("access")

        payload = client.list_my_clients()

        self.assertEqual(payload, {"clients": []})
        self.assertEqual(session.request.call_args.args[:2], ("GET", "http://api.local/therapists/me/clients"))
        self.assertEqual(session.request.call_args.kwargs["headers"]["Authorization"], "Bearer access")

    def test_timeout_handling(self):
        client, _session = self.make_client(side_effect=requests.Timeout("slow"))

        with self.assertRaises(APITimeoutError):
            client.health()

    def test_invalid_response_shape_raises_validation_error(self):
        client, _session = self.make_client(FakeResponse(payload={"username": "giulia"}))

        with self.assertRaises(APIResponseValidationError):
            client.login("giulia", "secret")

    def test_fallback_local_configuration_defaults_to_disabled(self):
        config = APIClientConfig.from_values(base_url="http://api.local", timeout_seconds="3")

        self.assertFalse(config.use_http_api)
        self.assertEqual(config.base_url, "http://api.local")
        self.assertEqual(config.timeout_seconds, 3.0)

    def test_login_regression_keeps_payload_shape(self):
        client, _session = self.make_client(
            FakeResponse(
                payload={
                    "username": "mario",
                    "authenticated": True,
                    "metadata": {"role": "therapist", "subscription_status": "trialing"},
                    "profile": {"nome": "Mario"},
                }
            )
        )

        payload = client.login("mario", "supersecret")

        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["metadata"]["role"], "therapist")
        self.assertEqual(payload["profile"]["nome"], "Mario")

    def test_client_dashboard_wellness_regression_keeps_existing_fields(self):
        wellness = {
            "mood_entries": [{"data": "2026-05-18", "ansia": 6, "stress": 5, "umore_intensita": 7}],
            "homework_assignments": [],
            "homework_submissions": [],
            "timeline_events": [],
        }
        client, _session = self.make_client(FakeResponse(payload={"username": "cliente", "wellness": wellness}))

        payload = client.get_wellness("cliente")

        self.assertEqual(payload["mood_entries"][0]["ansia"], 6)
        self.assertIn("homework_assignments", payload)
        self.assertIn("timeline_events", payload)

    def test_homework_http_flow_parses_assignments_and_submissions(self):
        payload = {
            "username": "giulia",
            "assignments": [{"id": "hw1", "template": "Nota per la seduta"}],
            "submissions": [{"assignment_id": "hw1", "template": "Nota per la seduta"}],
            "statuses": [{"assignment_id": "hw1", "status": "Completato"}],
        }
        client, session = self.make_client(FakeResponse(payload=payload))

        response = client.get_homework("giulia")

        self.assertEqual(response, payload)
        session.request.assert_called_once_with(
            "GET",
            "http://api.local/clients/giulia/homework",
            json=None,
            headers={"Accept": "application/json", "X-Username": "giulia"},
            timeout=2.5,
        )

    def test_homework_assignment_and_submission_posts_preserve_shapes(self):
        wellness = {"homework_assignments": [{"id": "hw1"}], "homework_submissions": []}
        assignment_payload = {
            "username": "giulia",
            "assignment": {"id": "hw1", "template": "Nota per la seduta"},
            "wellness": wellness,
        }
        client, session = self.make_client(FakeResponse(payload=assignment_payload))

        response = client.create_homework_assignment(
            "giulia",
            {"template": "Nota per la seduta", "due_date": "2026-05-20", "assigned_by": "terapeuta"},
        )

        self.assertEqual(response["wellness"], wellness)
        self.assertEqual(session.request.call_args.args[:2], ("POST", "http://api.local/clients/giulia/homework-assignments"))

        submission_payload = {
            "username": "giulia",
            "submission": {"assignment_id": "hw1", "template": "Nota per la seduta"},
            "wellness": {"homework_assignments": [{"id": "hw1"}], "homework_submissions": [{"assignment_id": "hw1"}]},
        }
        client, session = self.make_client(FakeResponse(payload=submission_payload))

        response = client.create_homework_submission(
            "giulia",
            {"assignment_id": "hw1", "template": "Nota per la seduta", "prompt": "Scrivi", "answer": "Ok"},
        )

        self.assertEqual(response["submission"]["assignment_id"], "hw1")
        self.assertEqual(session.request.call_args.args[:2], ("POST", "http://api.local/homework-submissions"))
        self.assertEqual(session.request.call_args.kwargs["json"]["username"], "giulia")

    def test_reports_http_flow_and_response_parsing(self):
        recap_payload = {
            "username": "giulia",
            "items": ["Schede ultime 2 settimane: 1", "Ansia media: 6.0/10"],
            "text": "- Schede ultime 2 settimane: 1\n- Ansia media: 6.0/10",
        }
        client, session = self.make_client(FakeResponse(payload=recap_payload))

        recap = client.get_weekly_recap("giulia")

        self.assertEqual(recap, recap_payload)
        self.assertEqual(session.request.call_args.args[:2], ("GET", "http://api.local/clients/giulia/weekly-recap"))

        report_payload = {
            "username": "giulia",
            "report": {
                "entries_count": 1,
                "avg_anxiety": 6.0,
                "avg_stress": 5.0,
                "insights": ["Trigger ricorrente: lavoro"],
                "alerts": [],
                "homework_total": 1,
                "homework_completed": 1,
                "homework_compliance": 100.0,
                "last_activity": "2026-05-18",
                "export_text": "RESOCONTO PSYHELPER",
                "sections": [{"title": "Trigger", "lines": ["- lavoro: 1"]}],
            },
        }
        client, session = self.make_client(FakeResponse(payload=report_payload))

        report = client.get_clinical_report("giulia")

        self.assertEqual(report["report"]["export_text"], "RESOCONTO PSYHELPER")
        self.assertEqual(session.request.call_args.args[:2], ("GET", "http://api.local/clients/giulia/clinical-report"))

    def test_http_error_handling_for_migrated_homework_and_reports(self):
        client, _session = self.make_client(FakeResponse(status_code=500, payload={"error": {"message": "boom"}}))

        with self.assertRaises(APIHTTPError):
            client.get_homework("giulia")
        with self.assertRaises(APIHTTPError):
            client.get_weekly_recap("giulia")


if __name__ == "__main__":
    unittest.main()
