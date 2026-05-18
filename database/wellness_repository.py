"""Wellness JSON persistence helpers for PsyHelper."""

import os

from database.json_storage import (
    atomic_write_json,
    load_json_file,
    validate_json_safe,
)


def default_wellness_data():
    return {
        "mood_entries": [],
        "homework_assignments": [],
        "homework_submissions": [],
        "timeline_events": [],
    }


def ensure_wellness_schema(wellness):
    wellness.setdefault("mood_entries", [])
    wellness.setdefault("homework_assignments", [])
    wellness.setdefault("homework_submissions", [])
    wellness.setdefault("timeline_events", [])
    # Older exports may include mindfulness logs; they are no longer shown in the clinical product.
    wellness.pop("mindfulness_log", None)
    return wellness


def wellness_path(account_dir):
    return os.path.join(account_dir, "wellness.pkl")


def wellness_json_path(account_dir):
    return os.path.join(account_dir, "wellness.json")


def normalize_wellness_data(wellness):
    if not isinstance(wellness, dict):
        wellness = default_wellness_data()
    wellness = ensure_wellness_schema(wellness)
    return validate_json_safe(wellness)


def load_wellness(account_dir):
    json_path = wellness_json_path(account_dir)
    if os.path.exists(json_path):
        try:
            return normalize_wellness_data(load_json_file(json_path))
        except Exception:
            return default_wellness_data()

    if os.path.exists(wellness_path(account_dir)):
        raise RuntimeError("Legacy storage detected. Run scripts/migrate_legacy_storage.py")
    return default_wellness_data()


def save_wellness(account_dir, wellness):
    atomic_write_json(
        wellness_json_path(account_dir),
        normalize_wellness_data(wellness),
    )


def save_wellness_for(username, wellness, user_dir):
    save_wellness(user_dir(username), wellness)
