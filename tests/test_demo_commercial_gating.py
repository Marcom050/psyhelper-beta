from dataclasses import replace

from core.settings import load_settings
from services import subscription_service
from services import subscription_access


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


def test_demo_access_allows_expired_therapist_and_linked_patient(monkeypatch):
    demo_settings = replace(subscription_access.SETTINGS, commercial_gating_enabled=False)
    monkeypatch.setattr(subscription_access, "SETTINGS", demo_settings)
    monkeypatch.setattr(
        subscription_access,
        "resolve_effective_subscription",
        lambda *_args, **_kwargs: {
            "tenant_id": "therapist",
            "owner_username": "therapist",
            "status": "past_due",
            "trial_ends_at": None,
            "grace_ends_at": None,
            "subscription_plan": None,
        },
    )
    for username in ("therapist", "linked_patient"):
        state = subscription_access.tenant_access_state(username)
        assert state["can_login"] and state["can_read"] and state["can_write"]
        assert state["limited_mode"] is False


def test_commercial_access_rules_remain_opt_in(monkeypatch):
    monkeypatch.setattr(
        subscription_access,
        "SETTINGS",
        replace(subscription_access.SETTINGS, commercial_gating_enabled=True),
    )
    monkeypatch.setattr(
        subscription_access,
        "resolve_effective_subscription",
        lambda *_args, **_kwargs: {
            "tenant_id": "therapist",
            "owner_username": "therapist",
            "status": "past_due",
        },
    )
    state = subscription_access.tenant_access_state("therapist")
    assert state["can_login"] is True
    assert state["can_read"] is True
    assert state["can_write"] is False
