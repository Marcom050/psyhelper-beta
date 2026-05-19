from datetime import UTC, datetime, timedelta

from services import auth_service, subscription_service


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


def test_subscription_dashboard_path_does_not_crash_if_trial_expires_at_is_legacy_naive():
    auth_service.create_user("therapist_naive", "pass", role="therapist", subscription_status="trialing")
    metadata = auth_service.load_user_metadata("therapist_naive")
    metadata["subscription_expires_at"] = datetime.now().isoformat(timespec="seconds")
    auth_service.save_user_metadata("therapist_naive", metadata)

    active = subscription_service.is_subscription_active_for("therapist_naive", {"trialing", "active"})

    assert active is False
