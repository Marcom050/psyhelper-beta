"""Authentication and account helpers for PsyHelper.

The functions in this module deliberately avoid Streamlit dependencies so they can
be exercised independently from the UI flow. Persistence is delegated to
repository objects; by default the filesystem repositories use JSON files.
"""

from database.account_repository import (
    default_user_metadata,
    hash_password,
    is_valid_email,
    normalize_email,
    normalize_username,
    user_exists,
    verify_password,
)
from database.filesystem_account_repository import FilesystemAccountRepository
from database.filesystem_notes_repository import FilesystemNotesRepository
from database.filesystem_wellness_repository import FilesystemWellnessRepository
from database.wellness_repository import default_wellness_data, ensure_wellness_schema


def _account_repository(repository=None):
    return repository or FilesystemAccountRepository()


def _notes_repository(repository=None):
    return repository or FilesystemNotesRepository()


def _wellness_repository(repository=None):
    return repository or FilesystemWellnessRepository()


def load_account_bundle(username, repository=None):
    return _account_repository(repository).load_account_bundle(username)


def save_account_bundle(username, profile, messages, wellness, repository=None):
    return _account_repository(repository).save_account_bundle(username, profile, messages, wellness)


def load_user_metadata(username, repository=None):
    return _account_repository(repository).load_user_metadata(username)


def save_user_metadata(username, metadata, repository=None):
    return _account_repository(repository).save_user_metadata(username, metadata)


def create_user(
    username,
    password,
    role="client",
    therapist_username=None,
    subscription_status="inactive",
    profile=None,
    email=None,
    beta_disclaimer_accepted_at=None,
    repository=None,
):
    return _account_repository(repository).create_user(
        username,
        password,
        role=role,
        therapist_username=therapist_username,
        subscription_status=subscription_status,
        profile=profile,
        email=email,
        beta_disclaimer_accepted_at=beta_disclaimer_accepted_at,
    )


def create_client_account(therapist_username, client_username, password, display_name, repository=None):
    return create_user(
        client_username,
        password,
        role="client",
        therapist_username=therapist_username,
        subscription_status="covered_by_therapist",
        profile={"nome": display_name or normalize_username(client_username), "onboarding_completed": False},
        repository=repository,
    )


def therapist_email_exists(email, repository=None):
    return _account_repository(repository).therapist_email_exists(email)


def client_accounts_for(therapist_username, repository=None):
    return _account_repository(repository).client_accounts_for(therapist_username)


def load_therapist_notes(therapist_username, repository=None):
    return _notes_repository(repository).load_therapist_notes(therapist_username)


def save_therapist_notes(therapist_username, notes, repository=None):
    return _notes_repository(repository).save_therapist_notes(therapist_username, notes)


def save_wellness_for(username, wellness, repository=None):
    return _wellness_repository(repository).save_wellness(username, wellness)


__all__ = [
    "client_accounts_for",
    "create_client_account",
    "create_user",
    "default_user_metadata",
    "default_wellness_data",
    "ensure_wellness_schema",
    "hash_password",
    "is_valid_email",
    "load_account_bundle",
    "load_user_metadata",
    "load_therapist_notes",
    "normalize_email",
    "normalize_username",
    "save_account_bundle",
    "save_user_metadata",
    "save_wellness_for",
    "save_therapist_notes",
    "therapist_email_exists",
    "user_exists",
    "verify_password",
]
