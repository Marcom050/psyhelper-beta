"""JWT helpers for PsyHelper's minimal production-oriented API auth."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from typing import Any
from uuid import uuid4

try:  # Prefer PyJWT when available; keep a stdlib fallback for constrained deployments/tests.
    import jwt as _pyjwt
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    _pyjwt = None

from api.exceptions import AuthenticationError
from services import auth_service

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
TOKEN_ISSUER = os.getenv("TOKEN_ISSUER", "psyhelper-beta")
_DEVELOPMENT_SECRET = "psyhelper-beta-dev-secret-change-me"


@dataclass(frozen=True)
class AuthContext:
    """Typed user context returned by API auth dependencies."""

    username: str
    role: str
    therapist_username: str | None
    subscription_status: str
    metadata: dict[str, Any]
    profile: dict[str, Any]

    @property
    def is_therapist(self) -> bool:
        return self.role == "therapist"

    @property
    def is_client(self) -> bool:
        return self.role == "client"


def secret_key() -> str:
    """Return the JWT signing secret and fail closed in production-like environments."""

    value = os.getenv("SECRET_KEY") or os.getenv("PSYHELPER_SECRET_KEY")
    if value and len(value) >= 32:
        return value
    if value:
        raise RuntimeError("SECRET_KEY must be at least 32 characters for JWT signing")
    environment = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).lower()
    if environment in {"prod", "production"}:
        raise RuntimeError("SECRET_KEY is required in production")
    return _DEVELOPMENT_SECRET


def create_access_token(username: str) -> str:
    return _create_token(username, "access", timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(username: str) -> str:
    return _create_token(username, "refresh", timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


def verify_access_token(token: str) -> dict[str, Any]:
    payload = _decode_token(token)
    if payload.get("typ") != "access":
        raise AuthenticationError("Invalid access token")
    return payload


def verify_refresh_token(token: str) -> dict[str, Any]:
    payload = _decode_token(token)
    if payload.get("typ") != "refresh":
        raise AuthenticationError("Invalid refresh token")
    return payload


def auth_context_for_username(username: str) -> AuthContext:
    username = auth_service.normalize_username(username)
    if not username or not auth_service.user_exists(username):
        raise AuthenticationError("Unknown user")
    metadata = auth_service.load_user_metadata(username)
    bundle = auth_service.load_account_bundle(username)
    return AuthContext(
        username=username,
        role=str(metadata.get("role") or "client"),
        therapist_username=auth_service.normalize_username(metadata.get("therapist_username") or "") or None,
        subscription_status=str(metadata.get("subscription_status") or "inactive"),
        metadata=metadata,
        profile=bundle["profile"],
    )


def _create_token(username: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": auth_service.normalize_username(username),
        "typ": token_type,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "iss": TOKEN_ISSUER,
        "jti": str(uuid4()),
    }
    if _pyjwt is not None:
        return _pyjwt.encode(payload, secret_key(), algorithm=ALGORITHM)
    return _encode_hs256(payload, secret_key())


def _decode_token(token: str) -> dict[str, Any]:
    try:
        if _pyjwt is not None:
            payload = _pyjwt.decode(token, secret_key(), algorithms=[ALGORITHM], issuer=TOKEN_ISSUER)
        else:
            payload = _decode_hs256(token, secret_key())
    except Exception as exc:
        raise AuthenticationError("Invalid or expired token") from exc
    username = auth_service.normalize_username(payload.get("sub", ""))
    if not username:
        raise AuthenticationError("Invalid token subject")
    return payload


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _encode_hs256(payload: dict[str, Any], key: str) -> str:
    header = {"alg": ALGORITHM, "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def _decode_hs256(token: str, key: str) -> dict[str, Any]:
    header_b64, payload_b64, signature_b64 = token.split(".")
    signing_input = f"{header_b64}.{payload_b64}"
    expected = hmac.new(key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url(expected), signature_b64):
        raise AuthenticationError("Invalid token signature")
    header = json.loads(_b64url_decode(header_b64))
    if header.get("alg") != ALGORITHM:
        raise AuthenticationError("Invalid token algorithm")
    payload = json.loads(_b64url_decode(payload_b64))
    now = int(datetime.now(timezone.utc).timestamp())
    if int(payload.get("exp", 0)) < now or int(payload.get("nbf", 0)) > now:
        raise AuthenticationError("Expired token")
    if payload.get("iss") != TOKEN_ISSUER:
        raise AuthenticationError("Invalid token issuer")
    return payload
