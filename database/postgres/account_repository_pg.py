"""PostgreSQL JSONB-backed account repository."""

import logging

from database import config
from database import filesystem_account_repository as filesystem
from database.interfaces.account_repository_interface import AccountRepository
from database.postgres.connection import initialize_schema, connection
from database.postgres.jsonb import jsonb
from database.tenant_metadata import resolve_tenant_id, resolve_tenant_owner
from database.wellness_repository import ensure_wellness_schema

logger = logging.getLogger(__name__)


class PostgresAccountRepository(AccountRepository):
    """Store account profile, metadata, password hash, and messages in PostgreSQL JSONB."""

    def __init__(self):
        initialize_schema()

    def _filesystem_fallback_enabled(self):
        return bool(config.USE_FILESYSTEM_FALLBACK)

    def _warn_filesystem_fallback(self, operation, username=""):
        logger.warning("Filesystem fallback used operation=%s username=%s", operation, username)

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
            if not self._filesystem_fallback_enabled():
                return {"profile": {}, "messages": [], "wellness": ensure_wellness_schema({})}
            self._warn_filesystem_fallback("load_account_bundle", username)
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
            if not self._filesystem_fallback_enabled():
                return filesystem.normalize_user_metadata({}, username=username)
            self._warn_filesystem_fallback("load_user_metadata", username)
            return filesystem.load_user_metadata(username)
        return filesystem.normalize_user_metadata(row[0], username=username)

    def save_user_metadata(self, username, metadata):
        username = filesystem.normalize_username(username)
        metadata = filesystem.normalize_user_metadata(metadata, username=username)
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
        profile = filesystem.normalize_profile(profile or {})
        messages = filesystem.normalize_messages([])
        wellness = ensure_wellness_schema(filesystem.default_wellness_data())
        password_hash = filesystem.hash_password(password)
        metadata = filesystem.normalize_user_metadata(
            filesystem.default_user_metadata(
                role=role,
                therapist_username=therapist_username,
                subscription_status=subscription_status,
                email=email,
            ),
            username=username,
        )
        if beta_disclaimer_accepted_at:
            metadata["beta_disclaimer_accepted_at"] = beta_disclaimer_accepted_at
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO accounts (username, profile, metadata, password_hash)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (username) DO UPDATE SET
                        profile = EXCLUDED.profile,
                        metadata = EXCLUDED.metadata,
                        password_hash = EXCLUDED.password_hash
                    """,
                    (username, jsonb(profile), jsonb(metadata), password_hash),
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
        if self._filesystem_fallback_enabled():
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

    def _load_password_hash(self, username):
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT password_hash FROM accounts WHERE username = %s", (username,))
                row = cursor.fetchone()
        return row[0] if row and row[0] else None

    def _save_password_hash(self, username, password_hash):
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO accounts (username, profile, metadata, password_hash)
                    VALUES (%s, '{}'::jsonb, '{}'::jsonb, %s)
                    ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash
                    """,
                    (username, password_hash),
                )
            conn.commit()

    def verify_password(self, username, password):
        username = filesystem.normalize_username(username)
        stored_hash = self._load_password_hash(username)
        if stored_hash:
            if filesystem.is_argon2_hash(stored_hash):
                try:
                    verified = filesystem._password_hasher.verify(stored_hash, password)
                except (filesystem.InvalidHashError, filesystem.VerifyMismatchError, filesystem.VerificationError):
                    return False
                if verified and filesystem._password_hasher.check_needs_rehash(stored_hash):
                    self._save_password_hash(username, filesystem.hash_password(password))
                return verified
            if filesystem.is_legacy_sha256_hash(stored_hash) and stored_hash == filesystem.hash_password_legacy_sha256(password):
                self._save_password_hash(username, filesystem.hash_password(password))
                return True
            return False

        if not self._filesystem_fallback_enabled():
            return False
        logger.warning("Auth password_hash filesystem fallback used username=%s", username)
        if not filesystem.verify_password(username, password):
            return False
        try:
            with open(filesystem.password_hash_path(username), "r") as f:
                self._save_password_hash(username, f.read().strip())
        except Exception:
            logger.warning("Unable to sync filesystem password_hash to PostgreSQL username=%s", username)
        return True

    def user_exists(self, username):
        username = filesystem.normalize_username(username)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM accounts WHERE username = %s LIMIT 1", (username,))
                row = cursor.fetchone()
        if row:
            return True
        if not self._filesystem_fallback_enabled():
            return False
        self._warn_filesystem_fallback("user_exists", username)
        return filesystem.user_exists(username)

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
        if row:
            return True
        if not self._filesystem_fallback_enabled():
            return False
        self._warn_filesystem_fallback("therapist_email_exists")
        return filesystem.therapist_email_exists(email)

    def client_accounts_for(self, therapist_username):
        return self.get_clients_for_tenant(therapist_username)

    def get_clients_for_tenant(self, tenant_id):
        tenant_id = filesystem.normalize_username(tenant_id)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT username, profile, metadata FROM accounts
                    WHERE metadata->>'role' = 'client'
                      AND coalesce(metadata->>'tenant_id', metadata->>'therapist_username') = %s
                    ORDER BY username
                    """,
                    (tenant_id,),
                )
                rows = cursor.fetchall()
        clients = []
        for username, profile, metadata in rows:
            profile = filesystem.normalize_profile(profile)
            metadata = filesystem.normalize_user_metadata(metadata, username=username)
            clients.append({
                "username": username,
                "nome": profile.get("nome", username),
                "creato_il": metadata.get("created_at", ""),
            })
        if clients or not self._filesystem_fallback_enabled():
            return clients
        self._warn_filesystem_fallback("get_clients_for_tenant", tenant_id)
        return filesystem.client_accounts_for(tenant_id)

    def get_tenant_owner(self, tenant_id):
        tenant_id = filesystem.normalize_username(tenant_id)
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT username, profile, metadata FROM accounts
                    WHERE username = %s AND metadata->>'role' = 'therapist'
                    LIMIT 1
                    """,
                    (tenant_id,),
                )
                row = cursor.fetchone()
        if row:
            username, profile, metadata = row
            return {
                "username": username,
                "profile": filesystem.normalize_profile(profile),
                "metadata": filesystem.normalize_user_metadata(metadata, username=username),
            }
        if not self._filesystem_fallback_enabled():
            return None
        return FilesystemTenantFallback().get_tenant_owner(tenant_id)

    def is_same_tenant(self, user_a, user_b):
        metadata_a = self.load_user_metadata(user_a)
        metadata_b = self.load_user_metadata(user_b)
        tenant_a = resolve_tenant_id(metadata_a, user_a)
        tenant_b = resolve_tenant_id(metadata_b, user_b)
        same = bool(tenant_a and tenant_b and tenant_a == tenant_b)
        if not same:
            logger.warning(
                "Tenant access denied user_a=%s user_b=%s tenant_a=%s tenant_b=%s",
                user_a,
                user_b,
                tenant_a,
                tenant_b,
            )
        return same


class FilesystemTenantFallback:
    def get_tenant_owner(self, tenant_id):
        tenant_id = filesystem.normalize_username(tenant_id)
        if not filesystem.user_exists(tenant_id):
            return None
        metadata = filesystem.load_user_metadata(tenant_id)
        if metadata.get("role") != "therapist" or resolve_tenant_owner(metadata, tenant_id) != tenant_id:
            return None
        return {"username": tenant_id, "metadata": metadata, "profile": filesystem.load_account_bundle(tenant_id)["profile"]}
