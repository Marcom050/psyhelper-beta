from dataclasses import replace
from datetime import UTC, datetime, timedelta

from services import auth_service, subscription_service
import pytest


@pytest.fixture(autouse=True)
def commercial_gating(monkeypatch):
    monkeypatch.setattr(
        subscription_service,
        "SETTINGS",
        replace(subscription_service.SETTINGS, commercial_gating_enabled=True),
    )


def _trialing_metadata(expires_at):
    return {
        "role": "therapist",
        "subscription_status": "trialing",
        "subscription_expires_at": expires_at,
        "created_at": datetime.now(UTC).isoformat(),
    }


def test_trial_expiry_accepts_naive_datetime():
    metadata = _trialing_metadata(datetime.now() - timedelta(minutes=1))
    assert subscription_service.is_trial_expired(metadata) is True


def test_trial_expiry_accepts_aware_datetime():
    metadata = _trialing_metadata(datetime.now(UTC) - timedelta(minutes=1))
    assert subscription_service.is_trial_expired(metadata) is True


def test_trial_expiry_accepts_iso_string_without_timezone():
    metadata = _trialing_metadata((datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds"))
    assert subscription_service.is_trial_expired(metadata) is True


def test_trial_expiry_accepts_iso_string_with_timezone():
    metadata = _trialing_metadata((datetime.now(UTC) - timedelta(minutes=1)).isoformat(timespec="seconds"))
    assert subscription_service.is_trial_expired(metadata) is True


def test_subscription_dashboard_path_does_not_crash_if_trial_expires_at_is_legacy_naive(monkeypatch):
    monkeypatch.setattr(
        subscription_service,
        "SETTINGS",
        replace(subscription_service.SETTINGS, commercial_gating_enabled=True),
    )
    auth_service.create_user("therapist_naive", "pass", role="therapist", subscription_status="trialing")
    metadata = auth_service.load_user_metadata("therapist_naive")
    metadata["subscription_expires_at"] = datetime.now().isoformat(timespec="seconds")
    auth_service.save_user_metadata("therapist_naive", metadata)

    active = subscription_service.is_subscription_active_for("therapist_naive", {"trialing", "active"})

    assert active is False


def test_expired_trial_is_not_expired_in_demo_mode(monkeypatch):
    monkeypatch.setattr(
        subscription_service,
        "SETTINGS",
        replace(subscription_service.SETTINGS, commercial_gating_enabled=False),
    )
    metadata = _trialing_metadata(datetime.now(UTC) - timedelta(days=1))
    assert subscription_service.is_trial_expired(metadata) is False
