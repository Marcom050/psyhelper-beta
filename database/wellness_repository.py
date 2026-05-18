"""Wellness persistence helpers for PsyHelper.

This module migrates wellness storage from legacy pickle files to JSON while
separating wellness-specific data access from Streamlit and service-layer code.
"""

import os
import pickle

from database.json_storage import (
    atomic_write_json,
    json_path_for,
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
    # Migrazione: la vecchia app salvava log mindfulness; non viene più mostrato nel prodotto clinico.
    wellness.pop("mindfulness_log", None)
    return wellness


def wellness_path(account_dir):
    return os.path.join(account_dir, "wellness.pkl")


def wellness_json_path(account_dir):
    return json_path_for(wellness_path(account_dir))


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

    try:
        with open(wellness_path(account_dir), "rb") as f:
            wellness = pickle.load(f)
    except Exception:
        return default_wellness_data()

    try:
        wellness = normalize_wellness_data(wellness)
    except Exception:
        return default_wellness_data()

    try:
        atomic_write_json(json_path, wellness)
    except Exception:
        pass
    return wellness


def save_wellness(account_dir, wellness):
    atomic_write_json(
        wellness_json_path(account_dir),
        normalize_wellness_data(wellness),
    )


def save_wellness_for(username, wellness, user_dir):
    save_wellness(user_dir(username), wellness)
