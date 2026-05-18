"""Centralized migration utility for legacy PsyHelper pickle storage.

The script scans the local PsyHelper data root, asks the existing repository
loaders to migrate legacy ``.pkl`` files to JSON, leaves all legacy files in
place, and writes a machine-readable migration report.
"""

from __future__ import annotations

import json
import os
import pickle
import sys
import traceback
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Dict, Iterable, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from database import account_repository as accounts
from database.json_storage import atomic_write_json
from database.wellness_repository import normalize_wellness_data, wellness_json_path, wellness_path

LEGACY_FILES: Tuple[str, ...] = (
    "metadata",
    "profile",
    "messages",
    "wellness",
    "therapist_notes",
)


def data_root_for(users_dir: str | None = None) -> str:
    """Return the PsyHelper data root that contains the users directory."""
    return os.path.dirname(os.path.abspath(users_dir or accounts.USERS_DIR))


def report_path_for(users_dir: str | None = None) -> str:
    """Return the path where the migration report should be persisted."""
    return os.path.join(data_root_for(users_dir), "migration_report.json")


def empty_report() -> Dict[str, object]:
    """Build an empty migration report with stable key ordering."""
    return OrderedDict(
        [
            ("accounts_scanned", 0),
            ("accounts_migrated", 0),
            ("accounts_failed", 0),
            ("files_migrated", OrderedDict((name, 0) for name in LEGACY_FILES)),
            ("errors", []),
        ]
    )


def account_names(users_dir: str) -> Iterable[str]:
    """Yield account directory names from the users root in deterministic order."""
    if not os.path.isdir(users_dir):
        return []
    return [
        entry
        for entry in sorted(os.listdir(users_dir))
        if os.path.isdir(os.path.join(users_dir, entry))
    ]


def legacy_targets(account_name: str, account_dir: str) -> Dict[str, Tuple[str, str, Callable[[object], object]]]:
    """Return legacy/json paths and normalizers for one account."""
    return {
        "metadata": (
            accounts.metadata_path(account_dir),
            accounts.metadata_json_path(account_dir),
            accounts.normalize_user_metadata,
        ),
        "profile": (
            accounts.profile_path(account_dir),
            accounts.profile_json_path(account_dir),
            accounts.normalize_profile,
        ),
        "messages": (
            accounts.messages_path(account_dir),
            accounts.messages_json_path(account_dir),
            accounts.normalize_messages,
        ),
        "wellness": (
            wellness_path(account_dir),
            wellness_json_path(account_dir),
            normalize_wellness_data,
        ),
        "therapist_notes": (
            accounts.therapist_notes_path(account_name),
            accounts.therapist_notes_json_path(account_name),
            accounts.normalize_therapist_notes,
        ),
    }


def _synthetic_traceback() -> str:
    """Return a compact traceback suitable for a JSON report."""
    return "".join(traceback.format_exc(limit=4)).strip()


def _append_error(report: Dict[str, object], account_name: str, storage_name: str, legacy_path: str, message: str) -> None:
    report["errors"].append(
        {
            "account": account_name,
            "storage": storage_name,
            "legacy_path": legacy_path,
            "error": message,
            "traceback": _synthetic_traceback(),
        }
    )


def _force_json_from_legacy(
    account_name: str,
    storage_name: str,
    legacy_path: str,
    json_path: str,
    normalizer: Callable[[object], object],
    report: Dict[str, object],
) -> bool:
    """Create a missing JSON file from a legacy pickle without deleting pickle."""
    try:
        with open(legacy_path, "rb") as legacy_file:
            legacy_data = pickle.load(legacy_file)
        normalized_data = normalizer(legacy_data)
        atomic_write_json(json_path, normalized_data)
        return True
    except Exception as exc:
        _append_error(report, account_name, storage_name, legacy_path, str(exc))
        return False


def _load_account_repositories(account_name: str, pending_names: Iterable[str]) -> None:
    """Ask existing repository loaders to perform their built-in migrations."""
    pending_names = set(pending_names)
    if "metadata" in pending_names:
        accounts.load_user_metadata(account_name)
    if pending_names.intersection({"profile", "messages", "wellness"}):
        accounts.load_account_bundle(account_name)
    if "therapist_notes" in pending_names:
        accounts.load_therapist_notes(account_name)


def migrate_account(account_name: str, report: Dict[str, object]) -> bool:
    """Migrate one account and update the report. Return True when errors occur."""
    account_dir = accounts.user_dir(account_name)
    targets = legacy_targets(account_name, account_dir)
    pending = {
        name: target
        for name, target in targets.items()
        if os.path.exists(target[0]) and not os.path.exists(target[1])
    }

    if not pending:
        return False

    errors_before = len(report["errors"])
    migrated_files = set()

    try:
        _load_account_repositories(account_name, pending.keys())
    except Exception as exc:
        _append_error(report, account_name, "account", account_dir, str(exc))

    for storage_name, (legacy_path, json_path, normalizer) in pending.items():
        if os.path.exists(json_path):
            migrated_files.add(storage_name)
            continue
        if _force_json_from_legacy(account_name, storage_name, legacy_path, json_path, normalizer, report):
            migrated_files.add(storage_name)

    for storage_name in migrated_files:
        report["files_migrated"][storage_name] += 1

    if migrated_files:
        report["accounts_migrated"] += 1

    return len(report["errors"]) > errors_before


def migrate_legacy_storage(users_dir: str | None = None) -> Dict[str, object]:
    """Run the legacy storage migration and persist ``migration_report.json``."""
    if users_dir is not None:
        accounts.USERS_DIR = users_dir
    users_dir = accounts.USERS_DIR
    os.makedirs(users_dir, exist_ok=True)
    os.makedirs(data_root_for(users_dir), exist_ok=True)

    report = empty_report()
    failed_accounts = set()

    for account_name in account_names(users_dir):
        report["accounts_scanned"] += 1
        if migrate_account(account_name, report):
            failed_accounts.add(account_name)

    report["accounts_failed"] = len(failed_accounts)
    atomic_write_json(report_path_for(users_dir), report)
    return report


def main() -> int:
    report = migrate_legacy_storage()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
