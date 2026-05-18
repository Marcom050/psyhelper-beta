import tempfile
import unittest

from database import account_repository as accounts
from database import filesystem_account_repository as filesystem_accounts

from database.interfaces.account_repository_interface import AccountRepository
from database.interfaces.notes_repository_interface import NotesRepository
from database.interfaces.wellness_repository_interface import WellnessRepository
from services import auth_service
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

    def load_wellness(self, account_dir):
        return self.saved[account_dir]

    def save_wellness(self, account_dir, wellness):
        self.saved[account_dir] = wellness


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
        self.assertEqual(next(iter(wellness_repository.saved.values())), {"mood_entries": [{"mood": 4}]})

    def test_create_client_account_uses_injected_account_repository(self):
        repository = InMemoryAccountRepository()

        auth_service.create_client_account("dr_rossi", "Cliente A", "segreta", "Cliente A", repository=repository)

        self.assertEqual(repository.created_users[0]["username"], "Cliente A")
        self.assertEqual(repository.created_users[0]["therapist_username"], "dr_rossi")
        self.assertEqual(repository.created_users[0]["subscription_status"], "covered_by_therapist")


if __name__ == "__main__":
    unittest.main()
