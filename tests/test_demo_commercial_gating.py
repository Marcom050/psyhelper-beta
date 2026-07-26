from dataclasses import replace

from core.settings import load_settings
from services import subscription_service


def test_commercial_gating_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("COMMERCIAL_GATING_ENABLED", raising=False)
    assert load_settings().commercial_gating_enabled is False


def test_demo_access_does_not_require_subscription(monkeypatch):
    monkeypatch.setattr(
        subscription_service,
        "SETTINGS",
        replace(subscription_service.SETTINGS, commercial_gating_enabled=False),
    )
    monkeypatch.setattr(
        subscription_service,
        "subscription_state_for",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("billing lookup must not run in demo mode")),
    )
    assert subscription_service.is_subscription_active_for("demo", {"active"}) is True


def test_commercial_gating_can_still_be_enabled(monkeypatch):
    monkeypatch.setattr(
        subscription_service,
        "SETTINGS",
        replace(subscription_service.SETTINGS, commercial_gating_enabled=True),
    )
    monkeypatch.setattr(
        subscription_service,
        "subscription_state_for",
        lambda *_args, **_kwargs: {
            "subscription_status": "inactive",
            "billing_status": "inactive",
        },
    )
    assert subscription_service.is_subscription_active_for("demo", {"active"}) is False
