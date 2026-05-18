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


class TherapistNotesJsonMigrationTest(unittest.TestCase):
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

    def write_pickle_notes(self, username, notes):
        os.makedirs(accounts.user_dir(username), exist_ok=True)
        with open(accounts.therapist_notes_path(username), "wb") as f:
            pickle.dump(notes, f)

    def write_json_notes(self, username, notes):
        os.makedirs(accounts.user_dir(username), exist_ok=True)
        with open(accounts.therapist_notes_json_path(username), "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, allow_nan=False)

    def read_json_notes(self, username):
        with open(accounts.therapist_notes_json_path(username), "r", encoding="utf-8") as f:
            return json.load(f)

    def test_legacy_user_with_only_therapist_notes_pickle_is_loaded(self):
        username = "dr_legacy"
        notes = {"client_a": "Nota legacy", "client_b": "Seconda nota"}
        self.write_pickle_notes(username, notes)

        loaded = accounts.load_therapist_notes(username)

        self.assertEqual(loaded, notes)

    def test_therapist_notes_json_only_is_loaded_without_pickle(self):
        username = "dr_json"
        notes = {"client_a": "Nota JSON", "client_b": "Solo JSON"}
        self.write_json_notes(username, notes)

        loaded = accounts.load_therapist_notes(username)

        self.assertEqual(loaded, notes)
        self.assertFalse(os.path.exists(accounts.therapist_notes_path(username)))

    def test_pickle_notes_are_migrated_to_json(self):
        username = "dr_migrate"
        notes = {"client_a": "Da migrare", "client_b": "Persistita in JSON"}
        self.write_pickle_notes(username, notes)

        loaded = accounts.load_therapist_notes(username)

        self.assertEqual(loaded, notes)
        self.assertTrue(os.path.exists(accounts.therapist_notes_json_path(username)))
        self.assertEqual(self.read_json_notes(username), notes)

    def test_json_notes_take_precedence_over_pickle_without_overwriting_json(self):
        username = "dr_both"
        json_notes = {"client_a": "Nota JSON aggiornata"}
        pickle_notes = {"client_a": "Nota pickle vecchia", "client_b": "Non usare"}
        self.write_pickle_notes(username, pickle_notes)
        self.write_json_notes(username, json_notes)

        loaded = accounts.load_therapist_notes(username)

        self.assertEqual(loaded, json_notes)
        self.assertEqual(self.read_json_notes(username), json_notes)

    def test_save_therapist_notes_writes_json_only_and_does_not_update_pickle(self):
        username = "dr_save"
        legacy_notes = {"client_a": "Legacy immutata"}
        self.write_pickle_notes(username, legacy_notes)

        accounts.save_therapist_notes(username, {"client_a": "Aggiornata", "client_b": "Nuova"})

        with open(accounts.therapist_notes_path(username), "rb") as f:
            self.assertEqual(pickle.load(f), legacy_notes)
        self.assertEqual(self.read_json_notes(username), {"client_a": "Aggiornata", "client_b": "Nuova"})

    def test_invalid_notes_data_is_filtered(self):
        username = "dr_invalid"
        notes = {
            "client_string": "Nota valida",
            123: "chiave non stringa scartata",
            "client_int": 42,
            "client_bool": True,
            "client_float": 3.5,
            "client_none": None,
            "client_list": ["non sicuro"],
            "client_dict": {"non": "sicuro"},
            "client_nan": float("nan"),
        }
        self.write_pickle_notes(username, notes)

        loaded = accounts.load_therapist_notes(username)

        expected = {
            "client_string": "Nota valida",
            "client_int": "42",
            "client_bool": "True",
            "client_float": "3.5",
        }
        self.assertEqual(loaded, expected)
        self.assertEqual(self.read_json_notes(username), expected)

    def test_unicode_notes_are_preserved(self):
        username = "dr_unicode"
        notes = {
            "cliente_zoe": "Zoë 🌱: ansia ridotta, sonno migliorato, più serenità 💜",
        }
        self.write_pickle_notes(username, notes)

        loaded = accounts.load_therapist_notes(username)

        self.assertEqual(loaded, notes)
        self.assertEqual(self.read_json_notes(username), notes)

    def test_corrupt_files_fall_back_to_empty_notes(self):
        username = "dr_corrupt"
        self.account_dir(username)
        with open(accounts.therapist_notes_path(username), "wb") as f:
            f.write(b"not a pickle")
        self.assertEqual(accounts.load_therapist_notes(username), {})

        with open(accounts.therapist_notes_json_path(username), "w", encoding="utf-8") as f:
            f.write("{not valid json")
        self.assertEqual(accounts.load_therapist_notes(username), {})


if __name__ == "__main__":
    unittest.main()
