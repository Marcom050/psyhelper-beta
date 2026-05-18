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


if __name__ == "__main__":
    unittest.main()
