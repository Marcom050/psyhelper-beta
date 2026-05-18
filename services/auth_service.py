"""Authentication and account helpers for PsyHelper.

The functions in this module deliberately avoid Streamlit dependencies so they can
be exercised independently from the UI flow. Persistence is delegated to the
``database`` repository layer, which currently preserves the existing pickle-based
storage layout.
"""

from database.account_repository import (
    USERS_DIR,
    client_accounts_for,
    create_client_account,
    create_user,
    default_user_metadata,
    hash_password,
    is_valid_email,
    load_account_bundle,
    load_user_metadata,
    load_therapist_notes,
    normalize_email,
    normalize_username,
    save_account_bundle,
    save_user_metadata,
    save_wellness_for,
    save_therapist_notes,
    therapist_email_exists,
    therapist_notes_json_path,
    therapist_notes_path,
    user_dir,
    user_exists,
    verify_password,
)
from database.wellness_repository import default_wellness_data, ensure_wellness_schema

__all__ = [
    "USERS_DIR",
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
    "therapist_notes_json_path",
    "therapist_notes_path",
    "user_dir",
    "user_exists",
    "verify_password",
]
