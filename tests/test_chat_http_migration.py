import importlib
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit as st

from clients.exceptions import APIConnectionError


class ChatHTTPMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st.secrets = {}
        cls.app = importlib.import_module("psyhelper_streamlit")

    def patch_chat_context(self, username="giulia", profile=None, wellness=None):
        profile = profile if profile is not None else {"nome": "Giulia"}
        wellness = wellness if wellness is not None else {"mood_entries": []}
        return patch.multiple(
            self.app.session_adapter,
            get_profile=Mock(return_value=profile),
            get_wellness=Mock(return_value=wellness),
            get_username=Mock(return_value=username),
        )

    def test_chat_http_success_flow_uses_api_client_only(self):
        fake_client = Mock()
        fake_client.chat_message.return_value = {"username": "giulia", "content": "Risposta HTTP"}

        with self.patch_chat_context(), patch.object(self.app, "use_http_api", return_value=True), patch.object(
            self.app, "api_client", return_value=fake_client
        ), patch.object(self.app, "get_local_chat_response") as local_mock:
            reply = self.app.get_response("Sono in ansia")

        self.assertEqual(reply, "Risposta HTTP")
        fake_client.chat_message.assert_called_once_with(
            "giulia",
            "Sono in ansia",
            {"nome": "Giulia"},
            {"mood_entries": []},
        )
        local_mock.assert_not_called()

    def test_chat_fallback_locale_when_http_disabled(self):
        with self.patch_chat_context(), patch.object(self.app, "use_http_api", return_value=False), patch.object(
            self.app, "get_local_chat_response", return_value="Risposta locale"
        ) as local_mock, patch.object(self.app, "api_client") as api_client_mock:
            reply = self.app.get_response("Sono in ansia")

        self.assertEqual(reply, "Risposta locale")
        local_mock.assert_called_once()
        api_client_mock.assert_not_called()

    def test_chat_error_handling_falls_back_to_local_without_breaking_reply(self):
        fake_client = Mock()
        fake_client.chat_message.side_effect = APIConnectionError("API unreachable")

        with self.patch_chat_context(), patch.object(self.app, "use_http_api", return_value=True), patch.object(
            self.app, "api_client", return_value=fake_client
        ), patch.object(self.app, "get_local_chat_response", return_value="Risposta fallback") as local_mock:
            reply = self.app.get_response("Sono in ansia")

        self.assertEqual(reply, "Risposta fallback")
        fake_client.chat_message.assert_called_once()
        local_mock.assert_called_once()

    def test_session_state_regression_context_reads_existing_shapes(self):
        profile = {"nome": "Giulia", "onboarding_completed": True}
        wellness = {"mood_entries": [{"ansia": 7}], "homework_assignments": []}

        with self.patch_chat_context(username="cliente", profile=profile, wellness=wellness):
            context = self.app.chat_context_for("Aiutami")

        self.assertEqual(context.username, "cliente")
        self.assertEqual(context.user_input, "Aiutami")
        self.assertIs(context.profile, profile)
        self.assertIs(context.wellness, wellness)

    def test_chat_ux_regression_keeps_existing_streamlit_flow(self):
        source = Path("psyhelper_streamlit.py").read_text()

        self.assertIn('if user_input := st.chat_input(', source)
        self.assertIn('"Scrivi un messaggio…"', source)
        self.assertIn('session_adapter.get_messages().append({"role": "user", "content": user_input})', source)
        self.assertIn('with st.spinner("Sto pensando..."):', source)
        self.assertIn('session_adapter.get_messages().append({"role": "assistant", "content": reply})', source)
        self.assertIn("save_user_data(session_adapter.get_username())", source)


if __name__ == "__main__":
    unittest.main()
