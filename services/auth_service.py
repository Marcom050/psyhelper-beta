"""Authentication and account persistence helpers for PsyHelper.

The functions in this module deliberately avoid Streamlit dependencies so they can
be exercised independently from the UI flow.
"""

import hashlib
import os
import pickle
import re
from datetime import datetime

USERS_DIR = os.path.expanduser("~/psyhelper_data/users")
os.makedirs(USERS_DIR, exist_ok=True)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


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
    return {
        "role": role,
        "therapist_username": normalize_username(therapist_username) if therapist_username else None,
        "subscription_status": subscription_status,
        "email": normalize_email(email) if email else "",
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        "beta_disclaimer_accepted_at": None,
    }


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


def load_user_metadata(username):
    if not user_exists(username):
        return default_user_metadata(role="therapist", subscription_status="inactive")

    metadata_path = os.path.join(user_dir(username), "metadata.pkl")
    try:
        with open(metadata_path, "rb") as f:
            metadata = pickle.load(f)
    except Exception:
        # Compatibilità con account creati prima del modello psicologo/cliente:
        # li trattiamo come professionisti attivi per non bloccare gli utenti esistenti.
        metadata = default_user_metadata(role="therapist", subscription_status="active")

    metadata.setdefault("role", "client")
    metadata.setdefault("therapist_username", None)
    metadata.setdefault("subscription_status", "inactive")
    metadata.setdefault("email", "")
    metadata.setdefault("created_at", datetime.utcnow().isoformat(timespec="seconds"))
    metadata.setdefault("beta_disclaimer_accepted_at", None)
    return metadata


def save_user_metadata(username, metadata):
    os.makedirs(user_dir(username), exist_ok=True)
    with open(os.path.join(user_dir(username), "metadata.pkl"), "wb") as f:
        pickle.dump(metadata, f)


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
    with open(os.path.join(account_dir, "password.txt"), "w") as f:
        f.write(hash_password(password))
    with open(os.path.join(account_dir, "profile.pkl"), "wb") as f:
        pickle.dump(profile or {}, f)
    with open(os.path.join(account_dir, "messages.pkl"), "wb") as f:
        pickle.dump([], f)
    with open(os.path.join(account_dir, "wellness.pkl"), "wb") as f:
        pickle.dump(default_wellness_data(), f)
    metadata = default_user_metadata(
        role=role,
        therapist_username=therapist_username,
        subscription_status=subscription_status,
        email=email,
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
        with open(os.path.join(user_dir(username), "password.txt"), "r") as f:
            return f.read() == hash_password(password)
    except Exception:
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
            try:
                with open(os.path.join(user_dir(account_name), "profile.pkl"), "rb") as f:
                    account_email = normalize_email(pickle.load(f).get("email", ""))
            except Exception:
                account_email = ""
        if account_email == normalized_email:
            return True
    return False


def load_account_bundle(username):
    account_dir = user_dir(username)
    try:
        with open(os.path.join(account_dir, "profile.pkl"), "rb") as f:
            profile = pickle.load(f)
    except Exception:
        profile = {}
    try:
        with open(os.path.join(account_dir, "messages.pkl"), "rb") as f:
            messages = pickle.load(f)
    except Exception:
        messages = []
    try:
        with open(os.path.join(account_dir, "wellness.pkl"), "rb") as f:
            wellness = pickle.load(f)
    except Exception:
        wellness = default_wellness_data()
    if not isinstance(wellness, dict):
        wellness = default_wellness_data()
    return {"profile": profile, "messages": messages, "wellness": ensure_wellness_schema(wellness)}


def save_account_bundle(username, profile, messages, wellness):
    account_dir = user_dir(username)
    with open(os.path.join(account_dir, "profile.pkl"), "wb") as f:
        pickle.dump(profile, f)
    with open(os.path.join(account_dir, "messages.pkl"), "wb") as f:
        pickle.dump(messages, f)
    with open(os.path.join(account_dir, "wellness.pkl"), "wb") as f:
        pickle.dump(ensure_wellness_schema(wellness), f)


def save_wellness_for(username, wellness):
    account_dir = user_dir(username)
    os.makedirs(account_dir, exist_ok=True)
    with open(os.path.join(account_dir, "wellness.pkl"), "wb") as f:
        pickle.dump(ensure_wellness_schema(wellness), f)


def therapist_notes_path(therapist_username):
    return os.path.join(user_dir(therapist_username), "therapist_notes.pkl")


def load_therapist_notes(therapist_username):
    try:
        with open(therapist_notes_path(therapist_username), "rb") as f:
            notes = pickle.load(f)
    except Exception:
        notes = {}
    return notes if isinstance(notes, dict) else {}


def save_therapist_notes(therapist_username, notes):
    with open(therapist_notes_path(therapist_username), "wb") as f:
        pickle.dump(notes, f)


def client_accounts_for(therapist_username):
    clients = []
    therapist_username = normalize_username(therapist_username)
    for account_name in sorted(os.listdir(USERS_DIR)):
        if not user_exists(account_name):
            continue
        metadata = load_user_metadata(account_name)
        if metadata.get("role") == "client" and metadata.get("therapist_username") == therapist_username:
            profile_path = os.path.join(user_dir(account_name), "profile.pkl")
            try:
                with open(profile_path, "rb") as f:
                    profile = pickle.load(f)
            except Exception:
                profile = {}
            clients.append({
                "username": account_name,
                "nome": profile.get("nome", account_name),
                "creato_il": metadata.get("created_at", ""),
            })
    return clients
