import tempfile
import unittest
from pathlib import Path
from unittest import mock

from database import account_repository, config, filesystem_account_repository
from database.filesystem_account_repository import FilesystemAccountRepository
from database.filesystem_notes_repository import FilesystemNotesRepository
from database.filesystem_wellness_repository import FilesystemWellnessRepository
from database.postgres.account_repository_pg import PostgresAccountRepository
from database.postgres.notes_repository_pg import PostgresNotesRepository
from database.postgres.wellness_repository_pg import PostgresWellnessRepository
from database.repository_factory import (
    get_account_repository,
    get_notes_repository,
    get_wellness_repository,
)
from database.json_storage import load_json_file


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.queries.append((sql, params))

    def fetchone(self):
        if self.rows:
            return self.rows.pop(0)
        return None

    def fetchall(self):
        if self.rows:
            rows = self.rows
            self.rows = []
            return rows
        return []


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True


class ConnectionContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


class PostgresRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_account_dir = account_repository.USERS_DIR
        self.original_filesystem_dir = filesystem_account_repository.USERS_DIR
        account_repository.USERS_DIR = str(Path(self.tempdir.name) / "users")
        filesystem_account_repository.USERS_DIR = account_repository.USERS_DIR
        Path(account_repository.USERS_DIR).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        account_repository.USERS_DIR = self.original_account_dir
        filesystem_account_repository.USERS_DIR = self.original_filesystem_dir
        config.USE_POSTGRESQL = False
        self.tempdir.cleanup()

    def test_factory_switches_between_filesystem_and_postgres(self):
        config.USE_POSTGRESQL = False
        self.assertIsInstance(get_account_repository(), FilesystemAccountRepository)
        self.assertIsInstance(get_wellness_repository(), FilesystemWellnessRepository)
        self.assertIsInstance(get_notes_repository(), FilesystemNotesRepository)

        config.USE_POSTGRESQL = True
        with mock.patch("database.postgres.account_repository_pg.initialize_schema"), \
             mock.patch("database.postgres.wellness_repository_pg.initialize_schema"), \
             mock.patch("database.postgres.notes_repository_pg.initialize_schema"):
            self.assertIsInstance(get_account_repository(), PostgresAccountRepository)
            self.assertIsInstance(get_wellness_repository(), PostgresWellnessRepository)
            self.assertIsInstance(get_notes_repository(), PostgresNotesRepository)

    def test_postgres_account_repository_save_uses_username_keyed_jsonb_tables(self):
        cursor = FakeCursor()
        conn = FakeConnection(cursor)
        with mock.patch("database.postgres.account_repository_pg.initialize_schema"), \
             mock.patch("database.postgres.account_repository_pg.connection", return_value=ConnectionContext(conn)):
            repository = PostgresAccountRepository()
            repository.save_account_bundle(
                "Client A",
                {"nome": "Client A"},
                [{"role": "user", "content": "ciao"}],
                {"mood_entries": [], "homework_assignments": [], "homework_submissions": [], "timeline_events": []},
            )

        sql = "\n".join(query for query, _ in cursor.queries)
        self.assertIn("INSERT INTO accounts", sql)
        self.assertIn("INSERT INTO messages", sql)
        self.assertIn("INSERT INTO wellness", sql)
        self.assertIn("ON CONFLICT (username)", sql)
        self.assertTrue(conn.committed)

    def test_postgres_repositories_fallback_to_filesystem_when_record_missing(self):
        filesystem_account_repository.create_user(
            "client_a",
            "password",
            profile={"nome": "Client A"},
        )
        filesystem_account_repository.save_therapist_notes("therapist_a", {"client_a": "nota"})

        account_cursor = FakeCursor(rows=[None, None, None])
        wellness_cursor = FakeCursor(rows=[None])
        notes_cursor = FakeCursor(rows=[None])

        with mock.patch("database.postgres.account_repository_pg.initialize_schema"), \
             mock.patch("database.postgres.account_repository_pg.connection", return_value=ConnectionContext(FakeConnection(account_cursor))):
            bundle = PostgresAccountRepository().load_account_bundle("client_a")
        with mock.patch("database.postgres.wellness_repository_pg.initialize_schema"), \
             mock.patch("database.postgres.wellness_repository_pg.connection", return_value=ConnectionContext(FakeConnection(wellness_cursor))):
            wellness = PostgresWellnessRepository().load_wellness("client_a")
        with mock.patch("database.postgres.notes_repository_pg.initialize_schema"), \
             mock.patch("database.postgres.notes_repository_pg.connection", return_value=ConnectionContext(FakeConnection(notes_cursor))):
            notes = PostgresNotesRepository().load_therapist_notes("therapist_a")

        self.assertEqual(bundle["profile"]["nome"], "Client A")
        self.assertEqual(wellness["mood_entries"], [])
        self.assertEqual(notes, {"client_a": "nota"})

    def test_filesystem_repository_still_writes_current_json_layout(self):
        repository = FilesystemAccountRepository()
        repository.save_account_bundle(
            "client_b",
            {"nome": "Client B"},
            [{"role": "assistant", "content": "benvenuto"}],
            {"mood_entries": [], "homework_assignments": [], "homework_submissions": [], "timeline_events": []},
        )

        account_dir = Path(account_repository.user_dir("client_b"))
        self.assertEqual(load_json_file(account_dir / "profile.json"), {"nome": "Client B"})
        self.assertEqual(load_json_file(account_dir / "messages.json"), [{"role": "assistant", "content": "benvenuto"}])
        self.assertTrue((account_dir / "wellness.json").exists())


if __name__ == "__main__":
    unittest.main()
