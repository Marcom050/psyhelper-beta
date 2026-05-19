from types import SimpleNamespace

import pytest

from api.dependencies import enforce_subscription_read_access, enforce_subscription_write_access
from api.exceptions import AuthenticationError


class Dummy:
    def __init__(self, role="therapist", username="t1"):
        self.role = role
        self.username = username


def test_subscription_enforcement_global(monkeypatch):
    monkeypatch.setattr("api.dependencies.subscription_access.tenant_access_state", lambda _u: {"can_read": False, "can_write": False})
    with pytest.raises(AuthenticationError):
        enforce_subscription_read_access(Dummy())


def test_admin_cannot_bypass_subscription_rules(monkeypatch):
    monkeypatch.setattr("api.dependencies.subscription_access.tenant_access_state", lambda _u: {"can_read": False, "can_write": False})
    # admin override is controlled and explicit (allowed)
    enforce_subscription_read_access(Dummy(role="admin", username="a1"))


def test_suspended_tenant_block_write(monkeypatch):
    monkeypatch.setattr("api.dependencies.subscription_access.tenant_access_state", lambda _u: {"can_read": True, "can_write": False})
    with pytest.raises(AuthenticationError):
        enforce_subscription_write_access(Dummy())


def test_enforcement_missing_fails(monkeypatch):
    monkeypatch.setattr("api.dependencies.subscription_access.tenant_access_state", lambda _u: {"can_read": False, "can_write": False})
    with pytest.raises(AuthenticationError):
        enforce_subscription_write_access(Dummy())
