"""PostgreSQL JSONB-backed wellness repository."""

from database import filesystem_account_repository as filesystem
from database.interfaces.wellness_repository_interface import WellnessRepository
from database.postgres.connection import initialize_schema, connection
from database.postgres.jsonb import jsonb
from database.wellness_repository import normalize_wellness_data


class PostgresWellnessRepository(WellnessRepository):
    """Store wellness documents by username in PostgreSQL JSONB."""

    def __init__(self):
        initialize_schema()

    def load_wellness(self, username):
        username = filesystem.normalize_username(username)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT wellness FROM wellness WHERE username = %s", (username,))
                row = cursor.fetchone()
        if row is None:
            return filesystem.load_account_bundle(username)["wellness"]
        return normalize_wellness_data(row[0])

    def save_wellness(self, username, wellness):
        username = filesystem.normalize_username(username)
        wellness = normalize_wellness_data(wellness)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO wellness (username, wellness)
                    VALUES (%s, %s)
                    ON CONFLICT (username) DO UPDATE SET wellness = EXCLUDED.wellness
                    """,
                    (username, jsonb(wellness)),
                )
            conn.commit()
