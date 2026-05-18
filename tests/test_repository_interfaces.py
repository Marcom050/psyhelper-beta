import inspect
import os
import tempfile
import unittest

from database import account_repository as accounts
from database import filesystem_account_repository as filesystem_accounts
from database import wellness_repository as wellness_storage

from database.interfaces.account_repository_interface import AccountRepository
from database.interfaces.notes_repository_interface import NotesRepository
from database.interfaces.wellness_repository_interface import WellnessRepository
from database.filesystem_wellness_repository import FilesystemWellnessRepository
from services import auth_service
from services.homework_service import completed_assignment_ids, get_assigned_homework, get_submitted_homework
from services.report_service import clinical_snapshot
from services.subscription_service import is_subscription_active_for


class InMemoryAccountRepository(AccountRepository):
    def __init__(self):
        self.metadata = {}
        self.bundles = {}
        self.created_users = []

    def load_account_bundle(self, username):
        return self.bundles[username]

    def save_account_bundle(self, username, profile, messages, wellness):
        self.bundles[username] = {"profile": profile, "messages": messages, "wellness": wellness}

    def load_user_metadata(self, username):
        return self.metadata[username]

    def save_user_metadata(self, username, metadata):
        self.metadata[username] = metadata

    def create_user(
        self,
        username,
        password,
        role="client",
        therapist_username=None,
        subscription_status="inactive",
        profile=None,
        email=None,
        beta_disclaimer_accepted_at=None,
    ):
        self.created_users.append(
            {
                "username": username,
                "password": password,
                "role": role,
                "therapist_username": therapist_username,
                "subscription_status": subscription_status,
                "profile": profile,
                "email": email,
                "beta_disclaimer_accepted_at": beta_disclaimer_accepted_at,
            }
        )

    def therapist_email_exists(self, email):
        return any(metadata.get("email") == email for metadata in self.metadata.values())

    def client_accounts_for(self, therapist_username):
        return [
            {
                "username": username,
                "nome": self.bundles[username]["profile"].get("nome", username),
                "creato_il": metadata.get("created_at", ""),
            }
            for username, metadata in self.metadata.items()
            if metadata.get("role") == "client" and metadata.get("therapist_username") == therapist_username
        ]


class InMemoryWellnessRepository(WellnessRepository):
    def __init__(self):
        self.saved = {}

    def load_wellness(self, username):
        return self.saved[username]

    def save_wellness(self, username, wellness):
        self.saved[username] = wellness


class InMemoryNotesRepository(NotesRepository):
    def __init__(self):
        self.notes = {}

    def load_therapist_notes(self, therapist_username):
        return self.notes.get(therapist_username, {})

    def save_therapist_notes(self, therapist_username, notes):
        self.notes[therapist_username] = notes


class RepositoryInterfacesTest(unittest.TestCase):

    def test_service_functions_use_filesystem_repository_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_users_dir = accounts.USERS_DIR
            original_filesystem_users_dir = filesystem_accounts.USERS_DIR
            accounts.USERS_DIR = temp_dir
            filesystem_accounts.USERS_DIR = temp_dir
            try:
                auth_service.create_user("default_user", "password", profile={"nome": "Default"})
                bundle = auth_service.load_account_bundle("default_user")
                auth_service.save_account_bundle(
                    "default_user",
                    {"nome": "Updated"},
                    bundle["messages"],
                    bundle["wellness"],
                )

                self.assertTrue(auth_service.verify_password("default_user", "password"))
                self.assertEqual(auth_service.load_account_bundle("default_user")["profile"]["nome"], "Updated")
            finally:
                accounts.USERS_DIR = original_users_dir
                filesystem_accounts.USERS_DIR = original_filesystem_users_dir

    def test_service_functions_accept_mock_account_repository(self):
        repository = InMemoryAccountRepository()
        repository.metadata["dr_rossi"] = {"role": "therapist", "subscription_status": "active"}
        repository.metadata["client_a"] = {
            "role": "client",
            "therapist_username": "dr_rossi",
            "created_at": "2026-05-01T09:00:00",
        }

        auth_service.save_account_bundle(
            "client_a",
            {"nome": "Cliente A"},
            [{"role": "user", "content": "ciao"}],
            {"mood_entries": []},
            repository=repository,
        )

        self.assertEqual(
            auth_service.load_account_bundle("client_a", repository=repository)["profile"]["nome"],
            "Cliente A",
        )
        self.assertTrue(is_subscription_active_for("client_a", {"active"}, repository=repository))
        self.assertEqual(auth_service.client_accounts_for("dr_rossi", repository=repository)[0]["username"], "client_a")

    def test_service_functions_accept_mock_wellness_and_notes_repositories(self):
        wellness_repository = InMemoryWellnessRepository()
        notes_repository = InMemoryNotesRepository()

        auth_service.save_wellness_for("client_a", {"mood_entries": [{"mood": 4}]}, repository=wellness_repository)
        auth_service.save_therapist_notes("dr_rossi", {"client_a": "Nota"}, repository=notes_repository)

        self.assertEqual(notes_repository.notes["dr_rossi"], {"client_a": "Nota"})
        self.assertEqual(auth_service.load_therapist_notes("dr_rossi", repository=notes_repository), {"client_a": "Nota"})
        self.assertEqual(wellness_repository.saved["client_a"], {"mood_entries": [{"mood": 4}]})

    def test_wellness_repository_contract_uses_logical_username(self):
        load_params = list(inspect.signature(WellnessRepository.load_wellness).parameters)
        save_params = list(inspect.signature(WellnessRepository.save_wellness).parameters)

        self.assertEqual(load_params, ["self", "username"])
        self.assertEqual(save_params, ["self", "username", "wellness"])

    def test_filesystem_wellness_repository_preserves_existing_json_storage(self):
        wellness = {
            "mood_entries": [{"data": "2026-05-18", "ansia": 4, "stress": 3}],
            "homework_assignments": [{"id": "hw_1", "template": "Nota per la seduta"}],
            "homework_submissions": [{"assignment_id": "hw_1", "summary": "Completato"}],
            "timeline_events": [{"data": "2026-05-18T10:00:00", "tipo": "Evento clinico"}],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            original_users_dir = accounts.USERS_DIR
            original_filesystem_users_dir = filesystem_accounts.USERS_DIR
            accounts.USERS_DIR = temp_dir
            filesystem_accounts.USERS_DIR = temp_dir
            try:
                repository = FilesystemWellnessRepository()

                repository.save_wellness("client_a", wellness)
                json_path = wellness_storage.wellness_json_path(accounts.user_dir("client_a"))

                self.assertTrue(os.path.exists(json_path))
                self.assertEqual(wellness_storage.load_json_file(json_path), wellness)
                self.assertEqual(repository.load_wellness("client_a"), wellness)
            finally:
                accounts.USERS_DIR = original_users_dir
                filesystem_accounts.USERS_DIR = original_filesystem_users_dir

    def test_auth_service_wellness_boundary_has_no_filesystem_coupling(self):
        wellness_repository = InMemoryWellnessRepository()
        wellness = {
            "mood_entries": [],
            "homework_assignments": [],
            "homework_submissions": [],
            "timeline_events": [],
        }

        auth_service.save_wellness_for("client_a", wellness, repository=wellness_repository)
        source = inspect.getsource(auth_service.save_wellness_for)

        self.assertEqual(wellness_repository.saved, {"client_a": wellness})
        self.assertNotIn("user_dir", source)
        self.assertNotIn("account_dir", source)

    def test_client_dashboard_homework_and_report_regression_from_saved_wellness(self):
        wellness_repository = InMemoryWellnessRepository()
        wellness = {
            "mood_entries": [
                {
                    "data": "2026-05-18",
                    "umore": "Calmo",
                    "umore_intensita": 3,
                    "ansia": 2,
                    "stress": 3,
                    "trigger": "lavoro",
                    "sensazioni": ["Respiro regolare"],
                    "nota_professionista": "Monitorare stabilità.",
                }
            ],
            "homework_assignments": [{"id": "hw_1", "template": "Nota per la seduta", "due_date": "2026-05-20"}],
            "homework_submissions": [{"assignment_id": "hw_1", "template": "Nota per la seduta", "submitted_at": "2026-05-18T09:00:00", "summary": "Nota pronta"}],
            "timeline_events": [],
        }

        auth_service.save_wellness_for("client_dashboard", wellness, repository=wellness_repository)
        saved_wellness = wellness_repository.load_wellness("client_dashboard")
        snapshot = clinical_snapshot(saved_wellness)

        self.assertIs(get_assigned_homework(saved_wellness), saved_wellness["homework_assignments"])
        self.assertIs(get_submitted_homework(saved_wellness), saved_wellness["homework_submissions"])
        self.assertEqual(completed_assignment_ids(saved_wellness["homework_submissions"]), {"hw_1"})
        self.assertEqual(snapshot.entries_count, 1)
        self.assertEqual(snapshot.homework_total, 1)
        self.assertEqual(snapshot.homework_completed, 1)

    def test_create_client_account_uses_injected_account_repository(self):
        repository = InMemoryAccountRepository()

        auth_service.create_client_account("dr_rossi", "Cliente A", "segreta", "Cliente A", repository=repository)

        self.assertEqual(repository.created_users[0]["username"], "Cliente A")
        self.assertEqual(repository.created_users[0]["therapist_username"], "dr_rossi")
        self.assertEqual(repository.created_users[0]["subscription_status"], "covered_by_therapist")


if __name__ == "__main__":
    unittest.main()
