"""PostgreSQL JSONB-backed account repository."""

from database import filesystem_account_repository as filesystem
from database.interfaces.account_repository_interface import AccountRepository
from database.postgres.connection import initialize_schema, connection
from database.postgres.jsonb import jsonb
from database.wellness_repository import ensure_wellness_schema


class PostgresAccountRepository(AccountRepository):
    """Store account profile, metadata, and messages in PostgreSQL JSONB."""

    def __init__(self):
        initialize_schema()

    def load_account_bundle(self, username):
        username = filesystem.normalize_username(username)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT profile FROM accounts WHERE username = %s", (username,))
                account_row = cursor.fetchone()
                cursor.execute("SELECT messages FROM messages WHERE username = %s", (username,))
                messages_row = cursor.fetchone()
                cursor.execute("SELECT wellness FROM wellness WHERE username = %s", (username,))
                wellness_row = cursor.fetchone()

        if account_row is None and messages_row is None and wellness_row is None:
            return filesystem.load_account_bundle(username)

        profile = filesystem.normalize_profile(account_row[0] if account_row else {})
        messages = filesystem.normalize_messages(messages_row[0] if messages_row else [])
        wellness = ensure_wellness_schema(wellness_row[0] if wellness_row else {})
        return {"profile": profile, "messages": messages, "wellness": wellness}

    def save_account_bundle(self, username, profile, messages, wellness):
        username = filesystem.normalize_username(username)
        profile = filesystem.normalize_profile(profile)
        messages = filesystem.normalize_messages(messages)
        wellness = ensure_wellness_schema(wellness)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO accounts (username, profile, metadata)
                    VALUES (%s, %s, '{}'::jsonb)
                    ON CONFLICT (username) DO UPDATE SET profile = EXCLUDED.profile
                    """,
                    (username, jsonb(profile)),
                )
                cursor.execute(
                    """
                    INSERT INTO messages (username, messages)
                    VALUES (%s, %s)
                    ON CONFLICT (username) DO UPDATE SET messages = EXCLUDED.messages
                    """,
                    (username, jsonb(messages)),
                )
                cursor.execute(
                    """
                    INSERT INTO wellness (username, wellness)
                    VALUES (%s, %s)
                    ON CONFLICT (username) DO UPDATE SET wellness = EXCLUDED.wellness
                    """,
                    (username, jsonb(wellness)),
                )
            conn.commit()

    def load_user_metadata(self, username):
        username = filesystem.normalize_username(username)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT metadata FROM accounts WHERE username = %s", (username,))
                row = cursor.fetchone()
        if row is None:
            return filesystem.load_user_metadata(username)
        return filesystem.normalize_user_metadata(row[0])

    def save_user_metadata(self, username, metadata):
        username = filesystem.normalize_username(username)
        metadata = filesystem.normalize_user_metadata(metadata)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO accounts (username, profile, metadata)
                    VALUES (%s, '{}'::jsonb, %s)
                    ON CONFLICT (username) DO UPDATE SET metadata = EXCLUDED.metadata
                    """,
                    (username, jsonb(metadata)),
                )
            conn.commit()

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
        username = filesystem.normalize_username(username)
        filesystem.create_user(
            username,
            password,
            role=role,
            therapist_username=therapist_username,
            subscription_status=subscription_status,
            profile=profile,
            email=email,
            beta_disclaimer_accepted_at=beta_disclaimer_accepted_at,
        )
        bundle = filesystem.load_account_bundle(username)
        metadata = filesystem.load_user_metadata(username)
        self.save_user_metadata(username, metadata)
        self.save_account_bundle(username, bundle["profile"], bundle["messages"], bundle["wellness"])

    def therapist_email_exists(self, email):
        normalized_email = filesystem.normalize_email(email)
        if not normalized_email:
            return False
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1 FROM accounts
                    WHERE metadata->>'role' = 'therapist'
                      AND lower(coalesce(metadata->>'email', profile->>'email', '')) = %s
                    LIMIT 1
                    """,
                    (normalized_email,),
                )
                row = cursor.fetchone()
        return bool(row) or filesystem.therapist_email_exists(email)

    def client_accounts_for(self, therapist_username):
        therapist_username = filesystem.normalize_username(therapist_username)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT username, profile, metadata FROM accounts
                    WHERE metadata->>'role' = 'client'
                      AND metadata->>'therapist_username' = %s
                    ORDER BY username
                    """,
                    (therapist_username,),
                )
                rows = cursor.fetchall()
        clients = []
        for username, profile, metadata in rows:
            profile = filesystem.normalize_profile(profile)
            metadata = filesystem.normalize_user_metadata(metadata)
            clients.append({
                "username": username,
                "nome": profile.get("nome", username),
                "creato_il": metadata.get("created_at", ""),
            })
        return clients or filesystem.client_accounts_for(therapist_username)
