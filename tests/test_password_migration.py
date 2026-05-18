import hashlib
import importlib.util
import sys
import tempfile
import types
import unittest


class FakeInvalidHashError(Exception):
    pass


class FakeVerifyMismatchError(Exception):
    pass


class FakeVerificationError(Exception):
    pass


class FakePasswordHasher:
    def hash(self, password):
        digest = hashlib.sha256(f"argon2-test:{password}".encode()).hexdigest()
        return f"$argon2id$v=19$m=65536,t=3,p=4${digest}"

    def verify(self, stored_hash, password):
        expected_hash = self.hash(password)
        if stored_hash != expected_hash:
            raise FakeVerifyMismatchError("password mismatch")
        return True

    def check_needs_rehash(self, stored_hash):
        return False


def ensure_argon2_test_double_if_missing():
    if importlib.util.find_spec("argon2") is not None:
        return
    argon2_module = types.ModuleType("argon2")
    exceptions_module = types.ModuleType("argon2.exceptions")
    argon2_module.PasswordHasher = FakePasswordHasher
    exceptions_module.InvalidHashError = FakeInvalidHashError
    exceptions_module.VerifyMismatchError = FakeVerifyMismatchError
    exceptions_module.VerificationError = FakeVerificationError
    sys.modules["argon2"] = argon2_module
    sys.modules["argon2.exceptions"] = exceptions_module


ensure_argon2_test_double_if_missing()
from database import account_repository as accounts


class PasswordHashingMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_users_dir = accounts.USERS_DIR
        accounts.USERS_DIR = self.temp_dir.name
        self.addCleanup(setattr, accounts, "USERS_DIR", self.original_users_dir)

    def read_password_hash(self, username):
        with open(accounts.password_hash_path(username), "r") as f:
            return f.read().strip()

    def test_new_user_password_is_stored_as_argon2_hash(self):
        accounts.create_user("Nuovo Utente", "password-sicura")

        stored_hash = self.read_password_hash("nuovo_utente")

        self.assertTrue(accounts.is_argon2_hash(stored_hash))
        self.assertNotEqual(stored_hash, accounts.hash_password_legacy_sha256("password-sicura"))
        self.assertTrue(accounts.verify_password("nuovo_utente", "password-sicura"))

    def test_legacy_sha256_user_is_migrated_to_argon2_after_successful_login(self):
        username = "legacy_user"
        user_path = accounts.user_dir(username)
        accounts.os.makedirs(user_path, exist_ok=True)
        accounts.save_password_hash(username, accounts.hash_password_legacy_sha256("password-legacy"))

        self.assertTrue(accounts.verify_password(username, "password-legacy"))
        migrated_hash = self.read_password_hash(username)

        self.assertTrue(accounts.is_argon2_hash(migrated_hash))
        self.assertTrue(accounts.verify_password(username, "password-legacy"))

    def test_wrong_password_returns_false_without_migrating_legacy_hash(self):
        username = "legacy_wrong"
        user_path = accounts.user_dir(username)
        accounts.os.makedirs(user_path, exist_ok=True)
        legacy_hash = accounts.hash_password_legacy_sha256("password-corretta")
        accounts.save_password_hash(username, legacy_hash)

        self.assertFalse(accounts.verify_password(username, "password-errata"))
        self.assertEqual(self.read_password_hash(username), legacy_hash)


if __name__ == "__main__":
    unittest.main()
