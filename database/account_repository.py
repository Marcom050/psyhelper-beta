"""Compatibility facade for the filesystem account repository.

Service-layer code should depend on repository objects. This module preserves the
existing function-based API used by migrations, tests, and UI imports while
forwarding persistence behavior to ``database.filesystem_account_repository``.
"""

from database import filesystem_account_repository as _filesystem

os = _filesystem.os
USERS_DIR = _filesystem.USERS_DIR
PASSWORD_HASH_FILENAME = _filesystem.PASSWORD_HASH_FILENAME
ARGON2_PREFIX = _filesystem.ARGON2_PREFIX
LEGACY_SHA256_HEX_LENGTH = _filesystem.LEGACY_SHA256_HEX_LENGTH


def _sync_users_dir():
    _filesystem.USERS_DIR = USERS_DIR


def hash_password(password):
    return _filesystem.hash_password(password)


def hash_password_legacy_sha256(password):
    return _filesystem.hash_password_legacy_sha256(password)


def is_argon2_hash(stored_hash):
    return _filesystem.is_argon2_hash(stored_hash)


def is_legacy_sha256_hash(stored_hash):
    return _filesystem.is_legacy_sha256_hash(stored_hash)


def password_hash_path(username):
    _sync_users_dir()
    return _filesystem.password_hash_path(username)


def save_password_hash(username, password_hash):
    _sync_users_dir()
    return _filesystem.save_password_hash(username, password_hash)


def normalize_username(username):
    return _filesystem.normalize_username(username)


def normalize_email(email):
    return _filesystem.normalize_email(email)


def is_valid_email(email):
    return _filesystem.is_valid_email(email)


def user_dir(username):
    _sync_users_dir()
    return _filesystem.user_dir(username)


def user_exists(username):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().user_exists(username)


def default_user_metadata(role="client", therapist_username=None, subscription_status="inactive", email=None):
    return _filesystem.default_user_metadata(role, therapist_username, subscription_status, email)


def metadata_path(account_dir):
    return _filesystem.metadata_path(account_dir)


def metadata_json_path(account_dir):
    return _filesystem.metadata_json_path(account_dir)


def profile_path(account_dir):
    return _filesystem.profile_path(account_dir)


def profile_json_path(account_dir):
    return _filesystem.profile_json_path(account_dir)


def messages_path(account_dir):
    return _filesystem.messages_path(account_dir)


def messages_json_path(account_dir):
    return _filesystem.messages_json_path(account_dir)


def normalize_user_metadata(metadata, username=None):
    return _filesystem.normalize_user_metadata(metadata, username=username)


def load_user_metadata(username):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().load_user_metadata(username)


def save_user_metadata(username, metadata):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().save_user_metadata(username, metadata)


def normalize_profile(profile):
    return _filesystem.normalize_profile(profile)


def normalize_messages(messages):
    return _filesystem.normalize_messages(messages)


def load_profile(account_dir):
    return _filesystem.load_profile(account_dir)


def load_messages(account_dir):
    return _filesystem.load_messages(account_dir)


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
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().create_user(
        username,
        password,
        role=role,
        therapist_username=therapist_username,
        subscription_status=subscription_status,
        profile=profile,
        email=email,
        beta_disclaimer_accepted_at=beta_disclaimer_accepted_at,
    )


def create_client_account(therapist_username, client_username, password, display_name):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().create_user(
        client_username,
        password,
        role="client",
        therapist_username=therapist_username,
        subscription_status="covered_by_therapist",
        profile={"nome": display_name or normalize_username(client_username), "onboarding_completed": False},
    )


def verify_password(username, password):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().verify_password(username, password)


def therapist_email_exists(email):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().therapist_email_exists(email)


def load_account_bundle(username):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().load_account_bundle(username)


def save_account_bundle(username, profile, messages, wellness):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().save_account_bundle(username, profile, messages, wellness)


def save_wellness_for(username, wellness):
    _sync_users_dir()
    from database.repository_factory import get_wellness_repository
    return get_wellness_repository().save_wellness(username, wellness)


def therapist_notes_path(therapist_username):
    _sync_users_dir()
    return _filesystem.therapist_notes_path(therapist_username)


def therapist_notes_json_path(therapist_username):
    _sync_users_dir()
    return _filesystem.therapist_notes_json_path(therapist_username)


def normalize_therapist_notes(notes):
    return _filesystem.normalize_therapist_notes(notes)


def load_therapist_notes(therapist_username):
    _sync_users_dir()
    from database.repository_factory import get_notes_repository
    return get_notes_repository().load_therapist_notes(therapist_username)


def save_therapist_notes(therapist_username, notes):
    _sync_users_dir()
    from database.repository_factory import get_notes_repository
    return get_notes_repository().save_therapist_notes(therapist_username, notes)


def client_accounts_for(therapist_username):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().client_accounts_for(therapist_username)


def get_clients_for_tenant(tenant_id):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().get_clients_for_tenant(tenant_id)


def get_tenant_owner(tenant_id):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().get_tenant_owner(tenant_id)


def is_same_tenant(user_a, user_b):
    _sync_users_dir()
    from database.repository_factory import get_account_repository
    return get_account_repository().is_same_tenant(user_a, user_b)
