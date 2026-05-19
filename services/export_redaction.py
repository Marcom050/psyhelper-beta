"""Centralized redaction for privacy-safe data exports."""

from __future__ import annotations

from typing import Any

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "access_token",
    "refresh_token",
    "token",
    "token_jti",
    "token_family",
    "secret",
    "secret_key",
    "api_key",
    "provider_secret",
    "auth_security_state",
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if normalized in SENSITIVE_KEYS:
        return True
    return any(part in normalized for part in ("password", "token", "secret", "api_key", "private_key", "jti", "family"))


def redact_export_payload(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                continue
            out[key] = redact_export_payload(item)
        return out
    if isinstance(value, list):
        return [redact_export_payload(item) for item in value]
    return value
