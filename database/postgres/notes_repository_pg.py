"""PostgreSQL JSONB-backed therapist notes repository."""

from database import filesystem_account_repository as filesystem
from database.interfaces.notes_repository_interface import NotesRepository
from database.postgres.connection import initialize_schema, connection
from database.postgres.jsonb import jsonb


class PostgresNotesRepository(NotesRepository):
    """Store therapist notes by therapist username in PostgreSQL JSONB."""

    def __init__(self):
        initialize_schema()

    def load_therapist_notes(self, therapist_username):
        therapist_username = filesystem.normalize_username(therapist_username)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT notes FROM notes WHERE username = %s", (therapist_username,))
                row = cursor.fetchone()
        if row is None:
            return filesystem.load_therapist_notes(therapist_username)
        return filesystem.normalize_therapist_notes(row[0])

    def save_therapist_notes(self, therapist_username, notes):
        therapist_username = filesystem.normalize_username(therapist_username)
        notes = filesystem.normalize_therapist_notes(notes)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO notes (username, notes)
                    VALUES (%s, %s)
                    ON CONFLICT (username) DO UPDATE SET notes = EXCLUDED.notes
                    """,
                    (therapist_username, jsonb(notes)),
                )
            conn.commit()
