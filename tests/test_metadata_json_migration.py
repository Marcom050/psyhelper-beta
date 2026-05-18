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


class MetadataJsonMigrationTest(unittest.TestCase):
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

    def write_pickle_metadata(self, username, metadata):
        with open(accounts.metadata_path(self.account_dir(username)), "wb") as f:
            pickle.dump(metadata, f)

    def write_json_metadata(self, username, metadata):
        with open(accounts.metadata_json_path(self.account_dir(username)), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, allow_nan=False)

    def read_json_metadata(self, username):
        with open(accounts.metadata_json_path(accounts.user_dir(username)), "r", encoding="utf-8") as f:
            return json.load(f)

    def test_legacy_user_with_only_pickle_is_loaded_and_migrated_to_json(self):
        username = "legacy_client"
        legacy_metadata = {
            "role": "client",
            "therapist_username": "dr_rossi",
            "subscription_status": "covered_by_therapist",
            "email": "cliente@example.com",
            "created_at": "2026-05-01T09:00:00",
            "beta_disclaimer_accepted_at": "2026-05-02T10:00:00",
        }
        self.write_pickle_metadata(username, legacy_metadata)

        loaded = accounts.load_user_metadata(username)

        self.assertEqual(loaded, legacy_metadata)
        self.assertTrue(os.path.exists(accounts.metadata_json_path(accounts.user_dir(username))))
        self.assertEqual(self.read_json_metadata(username), legacy_metadata)

    def test_new_user_with_only_json_is_loaded_without_pickle(self):
        username = "json_user"
        metadata = {
            "role": "therapist",
            "therapist_username": None,
            "subscription_status": "active",
            "email": "terapeuta@example.com",
            "created_at": "2026-05-03T09:00:00",
            "beta_disclaimer_accepted_at": None,
        }
        self.write_json_metadata(username, metadata)

        loaded = accounts.load_user_metadata(username)

        self.assertEqual(loaded, metadata)
        self.assertFalse(os.path.exists(accounts.metadata_path(accounts.user_dir(username))))

    def test_json_takes_precedence_when_json_and_pickle_exist(self):
        username = "both_formats"
        json_metadata = {
            "role": "therapist",
            "therapist_username": None,
            "subscription_status": "active",
            "email": "json@example.com",
            "created_at": "2026-05-04T09:00:00",
            "beta_disclaimer_accepted_at": None,
        }
        pickle_metadata = {
            "role": "client",
            "therapist_username": "legacy_therapist",
            "subscription_status": "inactive",
            "email": "pickle@example.com",
            "created_at": "2026-05-01T09:00:00",
            "beta_disclaimer_accepted_at": "2026-05-02T10:00:00",
        }
        self.write_pickle_metadata(username, pickle_metadata)
        self.write_json_metadata(username, json_metadata)

        loaded = accounts.load_user_metadata(username)

        self.assertEqual(loaded, json_metadata)
        self.assertEqual(self.read_json_metadata(username), json_metadata)

    def test_metadata_is_merged_with_defaults_without_losing_valid_data(self):
        username = "partial_metadata"
        self.write_json_metadata(username, {"role": "client", "email": "utente@example.com", "custom_flag": True})

        loaded = accounts.load_user_metadata(username)

        self.assertEqual(loaded["role"], "client")
        self.assertEqual(loaded["email"], "utente@example.com")
        self.assertTrue(loaded["custom_flag"])
        self.assertIsNone(loaded["therapist_username"])
        self.assertEqual(loaded["subscription_status"], "inactive")
        self.assertIsInstance(loaded["created_at"], str)
        self.assertIsNone(loaded["beta_disclaimer_accepted_at"])

    def test_optional_missing_fields_are_added_from_defaults(self):
        username = "missing_optional"
        self.write_json_metadata(
            username,
            {
                "role": "client",
                "subscription_status": "inactive",
                "created_at": "2026-05-05T09:00:00",
            },
        )

        loaded = accounts.load_user_metadata(username)

        self.assertIn("therapist_username", loaded)
        self.assertIn("email", loaded)
        self.assertIn("beta_disclaimer_accepted_at", loaded)
        self.assertIsNone(loaded["therapist_username"])
        self.assertEqual(loaded["email"], "")
        self.assertIsNone(loaded["beta_disclaimer_accepted_at"])

    def test_corrupt_json_returns_default_metadata(self):
        username = "corrupt_json"
        account_dir = self.account_dir(username)
        with open(accounts.metadata_json_path(account_dir), "w", encoding="utf-8") as f:
            f.write("{not valid json")

        loaded = accounts.load_user_metadata(username)

        self.assertEqual(loaded["role"], "client")
        self.assertIsNone(loaded["therapist_username"])
        self.assertEqual(loaded["subscription_status"], "inactive")
        self.assertEqual(loaded["email"], "")
        self.assertIsNone(loaded["beta_disclaimer_accepted_at"])

    def test_save_user_metadata_writes_only_json(self):
        username = "save_json_only"
        metadata = {
            "role": "client",
            "therapist_username": None,
            "subscription_status": "inactive",
            "email": "accenti@example.com",
            "created_at": "2026-05-06T09:00:00",
            "beta_disclaimer_accepted_at": "2026-05-06T09:05:00",
        }

        accounts.save_user_metadata(username, metadata)

        self.assertTrue(os.path.exists(accounts.metadata_json_path(accounts.user_dir(username))))
        self.assertFalse(os.path.exists(accounts.metadata_path(accounts.user_dir(username))))
        self.assertEqual(self.read_json_metadata(username), metadata)


if __name__ == "__main__":
    unittest.main()
