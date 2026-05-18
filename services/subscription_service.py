"""Subscription and beta-trial business logic for PsyHelper."""

from datetime import datetime, timedelta

from services.auth_service import load_user_metadata

BETA_TRIAL_DAYS = 7


def parse_iso_datetime(value):
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def trial_expires_at(created_at):
    created_datetime = parse_iso_datetime(created_at) or datetime.utcnow()
    return created_datetime + timedelta(days=BETA_TRIAL_DAYS)


def trial_days_remaining(created_at):
    remaining = trial_expires_at(created_at) - datetime.utcnow()
    return max(0, remaining.days + (1 if remaining.seconds or remaining.microseconds else 0))


def is_trial_expired(metadata):
    if metadata.get("role") != "therapist":
        return False
    if metadata.get("subscription_status", "inactive").lower() != "trialing":
        return False
    return datetime.utcnow() >= trial_expires_at(metadata.get("created_at"))


def is_subscription_active_for(username, active_subscription_statuses, repository=None):
    metadata = load_user_metadata(username, repository=repository)
    if metadata.get("role") == "client":
        therapist_username = metadata.get("therapist_username")
        return bool(
            therapist_username
            and is_subscription_active_for(therapist_username, active_subscription_statuses, repository=repository)
        )

    subscription_status = metadata.get("subscription_status", "inactive").lower()
    if subscription_status == "trialing":
        return not is_trial_expired(metadata)
    return subscription_status in active_subscription_statuses
