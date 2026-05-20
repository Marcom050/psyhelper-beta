"""Filesystem-backed account repository implementation.

The repository uses JSON files for runtime account storage and does not connect
to PostgreSQL, Supabase, or any external database.
"""

import hashlib
import logging
import os
import re
import shutil
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError

from database.json_storage import (
    atomic_write_json,
    load_json_file,
    validate_json_safe,
)
from database.interfaces.account_repository_interface import AccountRepository
from database.tenant_metadata import normalize_tenant_metadata, resolve_tenant_id, resolve_tenant_owner
from database.wellness_repository import (
    default_wellness_data,
    ensure_wellness_schema,
    load_wellness,
    save_wellness,
)

USERS_DIR = os.path.expanduser("~/psyhelper_data/users")
PASSWORD_HASH_FILENAME = "password.txt"
ARGON2_PREFIX = "$argon2"
LEGACY_SHA256_HEX_LENGTH = 64
_password_hasher = PasswordHasher()
logger = logging.getLogger(__name__)
os.makedirs(USERS_DIR, exist_ok=True)


def hash_password(password):
    """Return an Argon2 password hash for newly stored credentials."""
    return _password_hasher.hash(password)


def hash_password_legacy_sha256(password):
    """Return the legacy SHA-256 digest used by existing accounts."""
    return hashlib.sha256(password.encode()).hexdigest()


def is_argon2_hash(stored_hash):
    return stored_hash.startswith(ARGON2_PREFIX)


def is_legacy_sha256_hash(stored_hash):
    return len(stored_hash) == LEGACY_SHA256_HEX_LENGTH and all(
        character in "0123456789abcdef" for character in stored_hash.lower()
    )


def password_hash_path(username):
    return os.path.join(user_dir(username), PASSWORD_HASH_FILENAME)


def save_password_hash(username, password_hash):
    with open(password_hash_path(username), "w") as f:
        f.write(password_hash)


def normalize_username(username):
    normalized = username.strip().lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_-]", "", normalized)


def normalize_email(email):
    return email.strip().lower()


def is_valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalize_email(email)))


def user_dir(username):
    return os.path.join(USERS_DIR, normalize_username(username))


def user_exists(username):
    return os.path.isdir(user_dir(username))


def default_user_metadata(role="client", therapist_username=None, subscription_status="inactive", email=None):
    metadata = {
        "role": role,
        "therapist_username": normalize_username(therapist_username) if therapist_username else None,
        "subscription_status": subscription_status,
        "email": normalize_email(email) if email else "",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "beta_disclaimer_accepted_at": None,
    }
    return normalize_tenant_metadata(metadata)


def metadata_path(account_dir):
    return os.path.join(account_dir, "metadata.pkl")


def metadata_json_path(account_dir):
    return os.path.join(account_dir, "metadata.json")


def profile_path(account_dir):
    return os.path.join(account_dir, "profile.pkl")


def profile_json_path(account_dir):
    return os.path.join(account_dir, "profile.json")


def messages_path(account_dir):
    return os.path.join(account_dir, "messages.pkl")


def messages_json_path(account_dir):
    return os.path.join(account_dir, "messages.json")


LEGACY_STORAGE_ERROR = "Legacy storage detected. Run scripts/migrate_legacy_storage.py"


def _raise_if_legacy_only(old_path, new_path):
    if os.path.exists(old_path) and not os.path.exists(new_path):
        raise RuntimeError(LEGACY_STORAGE_ERROR)


def _is_iso_string_or_none(value):
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def normalize_user_metadata(metadata, username=None):
    defaults = default_user_metadata()
    if not isinstance(metadata, dict):
        metadata = {}

    merged = {**defaults, **metadata}
    if "billing_status" not in metadata:
        merged.pop("billing_status", None)
    if "subscription_plan" not in metadata:
        merged.pop("subscription_plan", None)
    if "subscription_started_at" not in metadata:
        merged.pop("subscription_started_at", None)
    if "subscription_expires_at" not in metadata:
        merged.pop("subscription_expires_at", None)
    normalized = normalize_tenant_metadata(merged, username=username)
    if not isinstance(normalized.get("role"), str):
        normalized["role"] = defaults["role"]
    if not (isinstance(normalized.get("therapist_username"), str) or normalized.get("therapist_username") is None):
        normalized["therapist_username"] = defaults["therapist_username"]
    if not isinstance(normalized.get("subscription_status"), str):
        normalized["subscription_status"] = defaults["subscription_status"]
    if not (isinstance(normalized.get("email"), str) or normalized.get("email") is None):
        normalized["email"] = defaults["email"]
    if not _is_iso_string_or_none(normalized.get("created_at")):
        normalized["created_at"] = defaults["created_at"]
    if not _is_iso_string_or_none(normalized.get("beta_disclaimer_accepted_at")):
        normalized["beta_disclaimer_accepted_at"] = defaults["beta_disclaimer_accepted_at"]

    return validate_json_safe(normalized)


def load_user_metadata(username):
    if not user_exists(username):
        return default_user_metadata(role="therapist", subscription_status="inactive")

    account_dir = user_dir(username)
    json_path = metadata_json_path(account_dir)
    if os.path.exists(json_path):
        try:
            return normalize_user_metadata(load_json_file(json_path), username=username)
        except Exception:
            return default_user_metadata()

    _raise_if_legacy_only(metadata_path(account_dir), json_path)
    return default_user_metadata()


def save_user_metadata(username, metadata):
    os.makedirs(user_dir(username), exist_ok=True)
    atomic_write_json(metadata_json_path(user_dir(username)), normalize_user_metadata(metadata, username=username))


def normalize_profile(profile):
    if not isinstance(profile, dict):
        return {}
    return validate_json_safe(profile)


def normalize_messages(messages):
    if not isinstance(messages, list):
        return []

    normalized = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            continue
        normalized.append({"role": role, "content": content})
    return validate_json_safe(normalized)


def _load_json_or_default(json_path, normalizer, default):
    try:
        return normalizer(load_json_file(json_path))
    except Exception:
        return default


def load_profile(account_dir):
    json_path = profile_json_path(account_dir)
    if os.path.exists(json_path):
        return _load_json_or_default(json_path, normalize_profile, {})

    _raise_if_legacy_only(profile_path(account_dir), json_path)
    return {}


def load_messages(account_dir):
    json_path = messages_json_path(account_dir)
    if os.path.exists(json_path):
        return _load_json_or_default(json_path, normalize_messages, [])

    _raise_if_legacy_only(messages_path(account_dir), json_path)
    return []


def create_user(
    username,
    password,
    role="client",
    therapist_username=None,
    subscription_status="inactive",
    profile=None,
    email=None,
    beta_disclaimer_accepted_at=None,
):
    username = normalize_username(username)
    account_dir = user_dir(username)
    os.makedirs(account_dir, exist_ok=True)
    save_password_hash(username, hash_password(password))
    atomic_write_json(profile_json_path(account_dir), normalize_profile(profile or {}))
    atomic_write_json(messages_json_path(account_dir), normalize_messages([]))
    save_wellness(account_dir, default_wellness_data())
    metadata = normalize_user_metadata(
        default_user_metadata(
            role=role,
            therapist_username=therapist_username,
            subscription_status=subscription_status,
            email=email,
        ),
        username=username,
    )
    if beta_disclaimer_accepted_at:
        metadata["beta_disclaimer_accepted_at"] = beta_disclaimer_accepted_at
    save_user_metadata(username, metadata)


def create_client_account(therapist_username, client_username, password, display_name):
    create_user(
        client_username,
        password,
        role="client",
        therapist_username=therapist_username,
        subscription_status="covered_by_therapist",
        profile={"nome": display_name or normalize_username(client_username), "onboarding_completed": False},
    )


def verify_password(username, password):
    try:
        with open(password_hash_path(username), "r") as f:
            stored_hash = f.read().strip()
    except Exception:
        return False

    if is_argon2_hash(stored_hash):
        try:
            verified = _password_hasher.verify(stored_hash, password)
        except (InvalidHashError, VerifyMismatchError, VerificationError):
            return False
        if verified and _password_hasher.check_needs_rehash(stored_hash):
            save_password_hash(username, hash_password(password))
        return verified

    if is_legacy_sha256_hash(stored_hash) and stored_hash == hash_password_legacy_sha256(password):
        save_password_hash(username, hash_password(password))
        return True

    return False


def therapist_email_exists(email):
    normalized_email = normalize_email(email)
    if not normalized_email or not os.path.isdir(USERS_DIR):
        return False
    for account_name in os.listdir(USERS_DIR):
        if not user_exists(account_name):
            continue
        metadata = load_user_metadata(account_name)
        if metadata.get("role") != "therapist":
            continue
        account_email = normalize_email(metadata.get("email", ""))
        if not account_email:
            account_email = normalize_email(load_account_bundle(account_name)["profile"].get("email", ""))
        if account_email == normalized_email:
            return True
    return False


def load_account_bundle(username):
    account_dir = user_dir(username)
    profile = load_profile(account_dir)
    messages = load_messages(account_dir)
    wellness = load_wellness(account_dir)
    return {"profile": profile, "messages": messages, "wellness": ensure_wellness_schema(wellness)}


def save_account_bundle(username, profile, messages, wellness):
    account_dir = user_dir(username)
    atomic_write_json(profile_json_path(account_dir), normalize_profile(profile))
    atomic_write_json(messages_json_path(account_dir), normalize_messages(messages))
    save_wellness(account_dir, wellness)


def save_wellness_for(username, wellness):
    save_wellness(user_dir(username), wellness)


def therapist_notes_path(therapist_username):
    return os.path.join(user_dir(therapist_username), "therapist_notes.pkl")


def therapist_notes_json_path(therapist_username):
    return os.path.join(user_dir(therapist_username), "therapist_notes.json")


def _safe_note_value_to_string(value):
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value == value and value not in (float("inf"), float("-inf")):
        return str(value)
    return None


def normalize_therapist_notes(notes):
    if not isinstance(notes, dict):
        return {}

    normalized = {}
    for client_username, note in notes.items():
        if not isinstance(client_username, str):
            continue
        safe_note = _safe_note_value_to_string(note)
        if safe_note is None:
            continue
        normalized[client_username] = safe_note
    return validate_json_safe(normalized)


def load_therapist_notes(therapist_username):
    json_path = therapist_notes_json_path(therapist_username)
    if os.path.exists(json_path):
        return _load_json_or_default(json_path, normalize_therapist_notes, {})

    _raise_if_legacy_only(therapist_notes_path(therapist_username), json_path)
    return {}


def save_therapist_notes(therapist_username, notes):
    atomic_write_json(
        therapist_notes_json_path(therapist_username),
        normalize_therapist_notes(notes),
    )


def client_accounts_for(therapist_username):
    clients = []
    therapist_username = normalize_username(therapist_username)
    if not os.path.isdir(USERS_DIR):
        return clients
    logger.warning("Filesystem client scan fallback used for therapist=%s", therapist_username)
    for account_name in sorted(os.listdir(USERS_DIR)):
        if not user_exists(account_name):
            continue
        metadata = load_user_metadata(account_name)
        if metadata.get("role") == "client" and resolve_tenant_id(metadata, account_name) == therapist_username:
            profile = load_account_bundle(account_name)["profile"]
            clients.append({
                "username": account_name,
                "nome": profile.get("nome", account_name),
                "creato_il": metadata.get("created_at", ""),
            })
    return clients


class FilesystemAccountRepository(AccountRepository):
    """Preserve the current filesystem account storage layout."""

    def load_account_bundle(self, username):
        return load_account_bundle(username)

    def save_account_bundle(self, username, profile, messages, wellness):
        return save_account_bundle(username, profile, messages, wellness)

    def load_user_metadata(self, username):
        return load_user_metadata(username)

    def save_user_metadata(self, username, metadata):
        return save_user_metadata(username, metadata)

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
        return create_user(
            username,
            password,
            role=role,
            therapist_username=therapist_username,
            subscription_status=subscription_status,
            profile=profile,
            email=email,
            beta_disclaimer_accepted_at=beta_disclaimer_accepted_at,
        )

    def therapist_email_exists(self, email):
        return therapist_email_exists(email)

    def client_accounts_for(self, therapist_username):
        return client_accounts_for(therapist_username)

    def get_clients_for_tenant(self, tenant_id):
        return client_accounts_for(tenant_id)

    def get_tenant_owner(self, tenant_id):
        tenant_id = normalize_username(tenant_id)
        metadata = load_user_metadata(tenant_id)
        if metadata.get("role") == "therapist" and resolve_tenant_owner(metadata, tenant_id) == tenant_id:
            return {"username": tenant_id, "metadata": metadata, "profile": load_account_bundle(tenant_id)["profile"]}
        return None

    def is_same_tenant(self, user_a, user_b):
        metadata_a = load_user_metadata(user_a)
        metadata_b = load_user_metadata(user_b)
        tenant_a = resolve_tenant_id(metadata_a, user_a)
        tenant_b = resolve_tenant_id(metadata_b, user_b)
        same = bool(tenant_a and tenant_b and tenant_a == tenant_b)
        if not same:
            logger.warning("Tenant access denied user_a=%s user_b=%s tenant_a=%s tenant_b=%s", user_a, user_b, tenant_a, tenant_b)
        return same

    def user_exists(self, username):
        return user_exists(username)

    def verify_password(self, username, password):
        return verify_password(username, password)

    def delete_user_account(self, username):
        username = normalize_username(username)
        account_dir = user_dir(username)
        if os.path.isdir(account_dir):
            shutil.rmtree(account_dir)
