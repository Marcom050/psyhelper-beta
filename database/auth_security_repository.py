from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from core.settings import SETTINGS
from database.json_storage import atomic_write_json, load_json_file

_SECURITY_PATH = os.getenv("AUTH_SECURITY_STATE_PATH", os.path.expanduser("~/psyhelper_data/auth_security_state.json"))
_LOCK = Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_state() -> dict[str, Any]:
    return {"revoked_tokens": {}, "refresh_family": {}, "failed_logins": {}}


class AuthSecurityRepository:
    def __init__(self, path: str | None = None):
        self._path = path or _SECURITY_PATH

    def _load(self) -> dict[str, Any]:
        if not os.path.exists(self._path):
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            atomic_write_json(self._path, _default_state())
        state = load_json_file(self._path)
        if not isinstance(state, dict):
            raise RuntimeError("Invalid auth security persistence format")
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_json(self._path, state)

    def cleanup_expired(self) -> None:
        with _LOCK:
            state = self._load()
            now_ts = int(_utc_now().timestamp())
            state["revoked_tokens"] = {k: v for k, v in state.get("revoked_tokens", {}).items() if int(v.get("exp", 0)) > now_ts}
            state["failed_logins"] = {
                k: v
                for k, v in state.get("failed_logins", {}).items()
                if not v.get("lock_until") or int(v.get("lock_until", 0)) > now_ts
            }
            state["refresh_family"] = {k: v for k, v in state.get("refresh_family", {}).items() if isinstance(v, str) and v}
            self._save(state)

    def revoke_token(self, token: str, token_exp: int) -> None:
        with _LOCK:
            state = self._load()
            state.setdefault("revoked_tokens", {})[token] = {"exp": int(token_exp)}
            self._save(state)

    def is_token_revoked(self, token: str) -> bool:
        self.cleanup_expired()
        state = self._load()
        return token in state.get("revoked_tokens", {})

    def get_refresh_family(self, username: str) -> str | None:
        self.cleanup_expired()
        return self._load().get("refresh_family", {}).get(username)

    def set_refresh_family(self, username: str, family_id: str) -> None:
        with _LOCK:
            state = self._load()
            state.setdefault("refresh_family", {})[username] = family_id
            self._save(state)

    def login_state(self, username: str) -> dict[str, Any]:
        self.cleanup_expired()
        return self._load().get("failed_logins", {}).get(username, {"count": 0, "window_start": 0, "lock_until": 0})

    def record_login_failure(self, username: str) -> None:
        with _LOCK:
            state = self._load()
            entry = state.setdefault("failed_logins", {}).setdefault(username, {"count": 0, "window_start": int(_utc_now().timestamp()), "lock_until": 0})
            now = _utc_now()
            if int(now.timestamp()) - int(entry.get("window_start", 0)) > SETTINGS.login_rate_limit_window_sec:
                entry["count"] = 0
                entry["window_start"] = int(now.timestamp())
            entry["count"] = int(entry.get("count", 0)) + 1
            if entry["count"] >= SETTINGS.login_rate_limit_attempts:
                entry["lock_until"] = int((now + timedelta(seconds=SETTINGS.login_lockout_sec)).timestamp())
            self._save(state)

    def reset_login_failures(self, username: str) -> None:
        with _LOCK:
            state = self._load()
            state.setdefault("failed_logins", {}).pop(username, None)
            self._save(state)

    def is_locked(self, username: str) -> bool:
        lock_until = int(self.login_state(username).get("lock_until", 0) or 0)
        return lock_until > int(_utc_now().timestamp())


def get_auth_security_repository() -> AuthSecurityRepository:
    return AuthSecurityRepository()
