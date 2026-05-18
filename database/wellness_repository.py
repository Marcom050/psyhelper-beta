"""Wellness persistence helpers for PsyHelper.

This module keeps the existing pickle-based storage untouched while separating
wellness-specific data access from Streamlit and service-layer code.
"""

import os
import pickle


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


def load_wellness(account_dir):
    try:
        with open(wellness_path(account_dir), "rb") as f:
            wellness = pickle.load(f)
    except Exception:
        wellness = default_wellness_data()
    if not isinstance(wellness, dict):
        wellness = default_wellness_data()
    return ensure_wellness_schema(wellness)


def save_wellness(account_dir, wellness):
    os.makedirs(account_dir, exist_ok=True)
    with open(wellness_path(account_dir), "wb") as f:
        pickle.dump(ensure_wellness_schema(wellness), f)


def save_wellness_for(username, wellness, user_dir):
    save_wellness(user_dir(username), wellness)
