import importlib.machinery
import importlib.util
import json
import os
import pickle
import sys
import tempfile
import types
import unittest


class FakePasswordHasher:
    def hash(self, password):
        return f"$argon2id$test${password}"

    def verify(self, stored_hash, password):
        if stored_hash != self.hash(password):
            raise FakeArgon2Error("password mismatch")
        return True

    def check_needs_rehash(self, stored_hash):
        return False


class FakeArgon2Error(Exception):
    pass


def ensure_argon2_test_double_if_missing():
    if importlib.util.find_spec("argon2") is not None:
        return
    argon2_module = types.ModuleType("argon2")
    exceptions_module = types.ModuleType("argon2.exceptions")
    argon2_module.__spec__ = importlib.machinery.ModuleSpec("argon2", loader=None)
    exceptions_module.__spec__ = importlib.machinery.ModuleSpec("argon2.exceptions", loader=None)
    argon2_module.PasswordHasher = FakePasswordHasher
    exceptions_module.InvalidHashError = FakeArgon2Error
    exceptions_module.VerifyMismatchError = FakeArgon2Error
    exceptions_module.VerificationError = FakeArgon2Error
    sys.modules["argon2"] = argon2_module
    sys.modules["argon2.exceptions"] = exceptions_module


ensure_argon2_test_double_if_missing()
from database import account_repository as accounts


class ProfileMessagesJsonMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_users_dir = accounts.USERS_DIR
        accounts.USERS_DIR = self.temp_dir.name
        self.addCleanup(setattr, accounts, "USERS_DIR", self.original_users_dir)

    def account_dir(self, username):
        account_dir = accounts.user_dir(username)
        os.makedirs(account_dir, exist_ok=True)
        return account_dir

    def write_pickle_profile(self, username, profile):
        with open(accounts.profile_path(self.account_dir(username)), "wb") as f:
            pickle.dump(profile, f)

    def write_pickle_messages(self, username, messages):
        with open(accounts.messages_path(self.account_dir(username)), "wb") as f:
            pickle.dump(messages, f)

    def write_json_profile(self, username, profile):
        with open(accounts.profile_json_path(self.account_dir(username)), "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, allow_nan=False)

    def write_json_messages(self, username, messages):
        with open(accounts.messages_json_path(self.account_dir(username)), "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, allow_nan=False)

    def read_json_profile(self, username):
        with open(accounts.profile_json_path(accounts.user_dir(username)), "r", encoding="utf-8") as f:
            return json.load(f)

    def read_json_messages(self, username):
        with open(accounts.messages_json_path(accounts.user_dir(username)), "r", encoding="utf-8") as f:
            return json.load(f)

    def test_legacy_user_with_only_profile_and_messages_pickle_is_loaded_and_migrated(self):
        username = "legacy_user"
        profile = {"nome": "Giulia", "età": 34, "custom": {"valid": True}}
        messages = [
            {"role": "user", "content": "Ciao"},
            {"role": "assistant", "content": "Benvenuta"},
        ]
        self.write_pickle_profile(username, profile)
        self.write_pickle_messages(username, messages)

        bundle = accounts.load_account_bundle(username)

        self.assertEqual(bundle["profile"], profile)
        self.assertEqual(bundle["messages"], messages)
        self.assertEqual(self.read_json_profile(username), profile)
        self.assertEqual(self.read_json_messages(username), messages)

    def test_new_user_is_json_only_for_profile_and_messages(self):
        username = "nuovo_utente"
        profile = {"nome": "Nuovo", "onboarding_completed": False}

        accounts.create_user(username, "password", profile=profile)

        self.assertEqual(self.read_json_profile(username), profile)
        self.assertEqual(self.read_json_messages(username), [])
        self.assertFalse(os.path.exists(accounts.profile_path(accounts.user_dir(username))))
        self.assertFalse(os.path.exists(accounts.messages_path(accounts.user_dir(username))))

    def test_json_takes_precedence_over_pickle_without_overwriting_json(self):
        username = "both_formats"
        json_profile = {"nome": "JSON", "email": "json@example.com"}
        pickle_profile = {"nome": "Pickle", "email": "pickle@example.com"}
        json_messages = [{"role": "user", "content": "json"}]
        pickle_messages = [{"role": "user", "content": "pickle"}]
        self.write_pickle_profile(username, pickle_profile)
        self.write_pickle_messages(username, pickle_messages)
        self.write_json_profile(username, json_profile)
        self.write_json_messages(username, json_messages)

        bundle = accounts.load_account_bundle(username)

        self.assertEqual(bundle["profile"], json_profile)
        self.assertEqual(bundle["messages"], json_messages)
        self.assertEqual(self.read_json_profile(username), json_profile)
        self.assertEqual(self.read_json_messages(username), json_messages)

    def test_save_account_bundle_writes_only_json_for_profile_and_messages(self):
        username = "save_user"
        self.account_dir(username)
        legacy_profile = {"nome": "Legacy"}
        legacy_messages = [{"role": "user", "content": "legacy"}]
        self.write_pickle_profile(username, legacy_profile)
        self.write_pickle_messages(username, legacy_messages)

        accounts.save_account_bundle(
            username,
            {"nome": "Aggiornato"},
            [{"role": "assistant", "content": "Salvato"}],
            {},
        )

        with open(accounts.profile_path(accounts.user_dir(username)), "rb") as f:
            self.assertEqual(pickle.load(f), legacy_profile)
        with open(accounts.messages_path(accounts.user_dir(username)), "rb") as f:
            self.assertEqual(pickle.load(f), legacy_messages)
        self.assertEqual(self.read_json_profile(username), {"nome": "Aggiornato"})
        self.assertEqual(self.read_json_messages(username), [{"role": "assistant", "content": "Salvato"}])

    def test_invalid_messages_are_filtered_and_order_is_preserved(self):
        username = "invalid_messages"
        messages = [
            {"role": "user", "content": "Primo", "extra": "ignored"},
            {"role": "assistant", "content": 123},
            "not a dict",
            {"role": "assistant", "content": "Secondo"},
            {"content": "missing role"},
        ]
        self.write_pickle_messages(username, messages)

        bundle = accounts.load_account_bundle(username)

        self.assertEqual(
            bundle["messages"],
            [
                {"role": "user", "content": "Primo"},
                {"role": "assistant", "content": "Secondo"},
            ],
        )
        self.assertEqual(self.read_json_messages(username), bundle["messages"])

    def test_profile_preserves_valid_unknown_fields_and_unicode(self):
        username = "unicode_profile"
        profile = {
            "nome": "Zoë 🌱",
            "obiettivi": "Dormire meglio e gestire l’ansia",
            "campo_sconosciuto": ["válido", {"emoji": "💜"}],
        }
        self.write_pickle_profile(username, profile)

        bundle = accounts.load_account_bundle(username)

        self.assertEqual(bundle["profile"], profile)
        self.assertEqual(self.read_json_profile(username), profile)

    def test_profile_invalid_shape_defaults_to_empty_dict(self):
        username = "invalid_profile"
        self.write_pickle_profile(username, ["not", "a", "dict"])

        bundle = accounts.load_account_bundle(username)

        self.assertEqual(bundle["profile"], {})
        self.assertEqual(self.read_json_profile(username), {})

    def test_centralized_loaders_are_used_for_therapist_email_and_client_accounts(self):
        therapist = "dr_json"
        client = "client_json"
        accounts.create_user(
            therapist,
            "password",
            role="therapist",
            profile={"email": "therapist-json-profile@example.com"},
            email="",
        )
        accounts.create_user(
            client,
            "password",
            role="client",
            therapist_username=therapist,
            subscription_status="covered_by_therapist",
            profile={"nome": "Cliente JSON"},
        )

        self.assertTrue(accounts.therapist_email_exists("therapist-json-profile@example.com"))
        self.assertEqual(
            accounts.client_accounts_for(therapist)[0]["nome"],
            "Cliente JSON",
        )


if __name__ == "__main__":
    unittest.main()
