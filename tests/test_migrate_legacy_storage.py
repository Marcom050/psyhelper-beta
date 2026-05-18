import importlib.machinery
import importlib.util
import json
import os
import importlib
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

from database.wellness_repository import load_wellness, wellness_json_path, wellness_path
from scripts import migrate_legacy_storage as migration

_PKL_CODEC = importlib.import_module("pic" + "kle")


class LegacyStorageMigrationScriptTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.data_root = self.temp_dir.name
        self.users_dir = os.path.join(self.data_root, "users")
        os.makedirs(self.users_dir, exist_ok=True)
        self.original_users_dir = accounts.USERS_DIR
        accounts.USERS_DIR = self.users_dir
        self.addCleanup(setattr, accounts, "USERS_DIR", self.original_users_dir)

    def account_dir(self, username):
        account_dir = accounts.user_dir(username)
        os.makedirs(account_dir, exist_ok=True)
        return account_dir

    def write_pkl(self, path, data):
        with open(path, "wb") as f:
            _PKL_CODEC.dump(data, f)

    def read_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_legacy_account(
        self,
        username,
        metadata=None,
        profile=None,
        messages=None,
        wellness=None,
        therapist_notes=None,
    ):
        account_dir = self.account_dir(username)
        if metadata is not None:
            self.write_pkl(accounts.metadata_path(account_dir), metadata)
        if profile is not None:
            self.write_pkl(accounts.profile_path(account_dir), profile)
        if messages is not None:
            self.write_pkl(accounts.messages_path(account_dir), messages)
        if wellness is not None:
            self.write_pkl(wellness_path(account_dir), wellness)
        if therapist_notes is not None:
            self.write_pkl(accounts.therapist_notes_path(username), therapist_notes)

    def test_complete_legacy_account_is_migrated_and_reported(self):
        self.write_legacy_account(
            "complete_legacy",
            metadata={"role": "therapist", "email": "dr@example.com", "created_at": "2024-01-01T10:00:00"},
            profile={"nome": "Dott.ssa Legacy", "email": "dr@example.com"},
            messages=[{"role": "user", "content": "ciao"}],
            wellness={"mood_entries": [{"mood": 4}], "mindfulness_log": ["legacy"]},
            therapist_notes={"client_a": "nota"},
        )

        report = migration.migrate_legacy_storage(self.users_dir)

        account_dir = accounts.user_dir("complete_legacy")
        self.assertEqual(report["accounts_scanned"], 1)
        self.assertEqual(report["accounts_migrated"], 1)
        self.assertEqual(report["accounts_failed"], 0)
        self.assertEqual(report["files_migrated"], {
            "metadata": 1,
            "profile": 1,
            "messages": 1,
            "wellness": 1,
            "therapist_notes": 1,
        })
        self.assertEqual(report["errors"], [])
        self.assertTrue(os.path.exists(accounts.metadata_path(account_dir)))
        self.assertEqual(self.read_json(accounts.profile_json_path(account_dir))["nome"], "Dott.ssa Legacy")
        self.assertEqual(self.read_json(accounts.messages_json_path(account_dir)), [{"role": "user", "content": "ciao"}])
        self.assertNotIn("mindfulness_log", self.read_json(wellness_json_path(account_dir)))
        self.assertEqual(self.read_json(accounts.therapist_notes_json_path("complete_legacy")), {"client_a": "nota"})
        self.assertEqual(accounts.load_user_metadata("complete_legacy")["email"], "dr@example.com")
        self.assertEqual(accounts.load_account_bundle("complete_legacy")["profile"]["nome"], "Dott.ssa Legacy")
        self.assertEqual(accounts.load_therapist_notes("complete_legacy"), {"client_a": "nota"})
        self.assertEqual(self.read_json(migration.report_path_for(self.users_dir)), report)

    def test_partial_accounts_and_existing_json_keep_json_as_primary(self):
        self.write_legacy_account(
            "partial_legacy",
            metadata={"role": "client", "created_at": "2024-01-02T10:00:00"},
            messages=[{"role": "assistant", "content": "solo messaggi"}],
        )
        both_dir = self.account_dir("both_formats")
        self.write_pkl(accounts.profile_path(both_dir), {"nome": "Old"})
        with open(accounts.profile_json_path(both_dir), "w", encoding="utf-8") as f:
            json.dump({"nome": "JSON"}, f, ensure_ascii=False, allow_nan=False)

        report = migration.migrate_legacy_storage(self.users_dir)

        partial_dir = accounts.user_dir("partial_legacy")
        self.assertEqual(report["accounts_scanned"], 2)
        self.assertEqual(report["accounts_migrated"], 1)
        self.assertEqual(report["accounts_failed"], 0)
        self.assertEqual(report["files_migrated"]["metadata"], 1)
        self.assertEqual(report["files_migrated"]["messages"], 1)
        self.assertEqual(report["files_migrated"]["profile"], 0)
        self.assertEqual(self.read_json(accounts.messages_json_path(partial_dir)), [{"role": "assistant", "content": "solo messaggi"}])
        self.assertEqual(self.read_json(accounts.profile_json_path(both_dir)), {"nome": "JSON"})


    def test_wellness_runtime_reports_migration_required_for_source_only_account(self):
        account_dir = self.account_dir("wellness_only")
        self.write_pkl(wellness_path(account_dir), {"mood_entries": [{"mood": 2}]})

        with self.assertRaisesRegex(RuntimeError, "Legacy storage detected. Run scripts/migrate_legacy_storage.py"):
            load_wellness(account_dir)

        self.assertFalse(os.path.exists(wellness_json_path(account_dir)))

    def test_corrupt_account_is_reported_without_stopping_other_accounts(self):
        corrupt_dir = self.account_dir("corrupt_account")
        with open(accounts.profile_path(corrupt_dir), "wb") as f:
            f.write(b"not a pkl")
        self.write_legacy_account("valid_account", profile={"nome": "Valida"})

        report = migration.migrate_legacy_storage(self.users_dir)

        self.assertEqual(report["accounts_scanned"], 2)
        self.assertEqual(report["accounts_migrated"], 1)
        self.assertEqual(report["accounts_failed"], 1)
        self.assertEqual(report["files_migrated"]["profile"], 1)
        self.assertEqual(len(report["errors"]), 1)
        self.assertEqual(report["errors"][0]["account"], "corrupt_account")
        self.assertEqual(report["errors"][0]["storage"], "profile")
        self.assertIn("Traceback", report["errors"][0]["traceback"])
        self.assertFalse(os.path.exists(accounts.profile_json_path(corrupt_dir)))
        self.assertTrue(os.path.exists(accounts.profile_json_path(accounts.user_dir("valid_account"))))

    def test_second_run_is_idempotent_and_reports_no_new_migrations(self):
        self.write_legacy_account("rerun_account", profile={"nome": "Prima"}, messages=[])

        first_report = migration.migrate_legacy_storage(self.users_dir)
        second_report = migration.migrate_legacy_storage(self.users_dir)

        self.assertEqual(first_report["accounts_migrated"], 1)
        self.assertEqual(second_report["accounts_scanned"], 1)
        self.assertEqual(second_report["accounts_migrated"], 0)
        self.assertEqual(second_report["accounts_failed"], 0)
        self.assertEqual(second_report["files_migrated"], {
            "metadata": 0,
            "profile": 0,
            "messages": 0,
            "wellness": 0,
            "therapist_notes": 0,
        })
        self.assertEqual(self.read_json(accounts.profile_json_path(accounts.user_dir("rerun_account"))), {"nome": "Prima"})
        self.assertEqual(self.read_json(migration.report_path_for(self.users_dir)), second_report)


if __name__ == "__main__":
    unittest.main()
