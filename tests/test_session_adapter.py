from pathlib import Path
import unittest

from services.session_adapter import AppSessionData, SessionAdapter


class SessionAdapterTest(unittest.TestCase):
    def make_adapter(self, state=None, **overrides):
        self.saved_bundle = None

        def default_wellness():
            return {"mood_entries": [], "homework_assignments": [], "homework_submissions": [], "timeline_events": []}

        def load_bundle(username):
            return {
                "profile": {"nome": "Ada", "onboarding_completed": True},
                "messages": [{"role": "user", "content": f"ciao {username}"}],
                "wellness": {"mood_entries": [{"umore": "Sereno"}]},
            }

        def load_metadata(username):
            return {"role": "client", "username": username, "subscription_status": "covered_by_therapist"}

        def save_bundle(username, profile, messages, wellness):
            self.saved_bundle = {
                "username": username,
                "profile": profile,
                "messages": messages,
                "wellness": wellness,
            }

        def ensure_schema(wellness):
            wellness.setdefault("mood_entries", [])
            wellness.setdefault("homework_assignments", [])
            wellness.setdefault("homework_submissions", [])
            wellness.setdefault("timeline_events", [])
            return wellness

        kwargs = {
            "default_wellness_factory": default_wellness,
            "load_account_bundle_func": load_bundle,
            "load_user_metadata_func": load_metadata,
            "save_account_bundle_func": save_bundle,
            "ensure_wellness_schema_func": ensure_schema,
        }
        kwargs.update(overrides)
        return SessionAdapter(state if state is not None else {}, **kwargs)

    def test_initialize_defaults_populates_app_session_data_without_overwriting_existing_values(self):
        state = {"username": "utente", "logged_in": True, "profile": {"nome": "Existing"}}
        adapter = self.make_adapter(state)

        adapter.initialize_defaults()
        data = adapter.get_session_data()

        self.assertIsInstance(data, AppSessionData)
        self.assertEqual(data.username, "utente")
        self.assertTrue(data.logged_in)
        self.assertEqual(data.profile, {"nome": "Existing"})
        self.assertEqual(data.messages, [])
        self.assertEqual(data.wellness["mood_entries"], [])
        self.assertEqual(data.user_metadata, {})
        self.assertIsNone(data.selected_patient_username)
        self.assertFalse(data.analytics_consent)
        self.assertFalse(data.beta_disclaimer_accepted)
        self.assertFalse(data.scroll_to_top)

    def test_reset_for_logout_preserves_existing_key_names_and_default_shapes(self):
        state = {
            "username": "cliente",
            "logged_in": True,
            "profile": {"nome": "Cliente"},
            "messages": [{"role": "assistant", "content": "ok"}],
            "wellness": {"mood_entries": [{"umore": "Ansioso"}]},
            "user_metadata": {"role": "client"},
            "scroll_to_top": False,
        }
        adapter = self.make_adapter(state)

        adapter.reset_for_logout()

        self.assertFalse(state["logged_in"])
        self.assertIsNone(state["username"])
        self.assertEqual(state["user_metadata"], {})
        self.assertEqual(state["profile"], {})
        self.assertEqual(state["messages"], [])
        self.assertEqual(state["wellness"], {"mood_entries": [], "homework_assignments": [], "homework_submissions": [], "timeline_events": []})
        self.assertTrue(state["scroll_to_top"])

    def test_load_user_session_updates_only_session_state_from_persistence_bundle(self):
        state = {}
        adapter = self.make_adapter(state)

        adapter.load_user_session("cliente")

        self.assertEqual(state["user_metadata"], {"role": "client", "username": "cliente", "subscription_status": "covered_by_therapist"})
        self.assertEqual(state["profile"], {"nome": "Ada", "onboarding_completed": True})
        self.assertEqual(state["messages"], [{"role": "user", "content": "ciao cliente"}])
        self.assertEqual(state["wellness"], {"mood_entries": [{"umore": "Sereno"}]})

    def test_persist_user_session_uses_current_shapes_without_changing_storage_schema(self):
        state = {
            "username": "cliente",
            "profile": {"nome": "Ada"},
            "messages": [{"role": "assistant", "content": "benvenuta"}],
            "wellness": {"mood_entries": [], "homework_assignments": []},
        }
        adapter = self.make_adapter(state)

        adapter.persist_user_session()

        self.assertEqual(
            self.saved_bundle,
            {
                "username": "cliente",
                "profile": state["profile"],
                "messages": state["messages"],
                "wellness": state["wellness"],
            },
        )

    def test_no_direct_session_state_access_outside_adapter(self):
        forbidden = "st." + "session_state"
        repo_root = Path(__file__).resolve().parents[1]
        offenders = []
        for path in repo_root.rglob("*.py"):
            relative = path.relative_to(repo_root)
            if relative.parts[0] == "tests" or relative == Path("services/session_adapter.py"):
                continue
            if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                continue
            if forbidden in path.read_text():
                offenders.append(str(relative))

        self.assertEqual(offenders, [])

    def test_login_regression_state_loaded_after_successful_login_sequence(self):
        state = {}
        adapter = self.make_adapter(state)

        adapter.set_logged_in(True)
        adapter.set_username("cliente")
        adapter.set_scroll_to_top(True)
        adapter.load_user_session("cliente")

        self.assertTrue(adapter.is_logged_in())
        self.assertEqual(adapter.get_username(), "cliente")
        self.assertTrue(adapter.get_scroll_to_top())
        self.assertEqual(adapter.get_user_metadata()["role"], "client")
        self.assertEqual(adapter.get_profile()["nome"], "Ada")

    def test_client_dashboard_regression_authenticated_defaults_keep_client_data(self):
        state = {
            "username": "cliente",
            "profile": {"onboarding_completed": True},
            "messages": [],
            "wellness": {"mood_entries": []},
            "user_metadata": {"role": "client"},
        }
        adapter = self.make_adapter(state)

        adapter.ensure_authenticated_defaults()

        self.assertEqual(adapter.get_user_metadata()["role"], "client")
        self.assertTrue(adapter.get_profile()["onboarding_completed"])
        self.assertIn("homework_assignments", adapter.get_wellness())
        self.assertIn("homework_submissions", adapter.get_wellness())

    def test_therapist_dashboard_regression_selected_patient_state(self):
        state = {"user_metadata": {"role": "therapist"}}
        adapter = self.make_adapter(state)

        if adapter.get_selected_patient_username() not in ["p1", "p2"]:
            adapter.set_selected_patient_username("p1")
        adapter.set_selected_patient_username("p2")

        self.assertEqual(adapter.get_user_metadata()["role"], "therapist")
        self.assertEqual(adapter.get_selected_patient_username(), "p2")


if __name__ == "__main__":
    unittest.main()
