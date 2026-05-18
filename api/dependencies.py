"""Small backend-side dependencies for the temporary HTTP API."""

from __future__ import annotations

import os
from typing import Any, Type

from pydantic import BaseModel, ValidationError
from starlette.requests import Request

from api.exceptions import APIValidationError, AuthenticationError, NotFoundError
from services import auth_service


COPYRIGHT_POLICY = os.getenv(
    "PSYHELPER_COPYRIGHT_POLICY",
    "Non fornire testi protetti da copyright non forniti dall'utente; usa sintesi e indicazioni originali.",
)


def groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY", "")


def active_subscription_statuses() -> set[str]:
    configured = os.getenv("ACTIVE_SUBSCRIPTION_STATUSES", "active,trialing")
    return {status.strip().lower() for status in configured.split(",") if status.strip()}


def current_username(request: Request) -> str:
    username = auth_service.normalize_username(request.headers.get("x-username", ""))
    if not username:
        raise AuthenticationError("Missing X-Username header")
    if not auth_service.user_exists(username):
        raise AuthenticationError("Unknown user")
    return username


def account_bundle(username: str) -> dict[str, Any]:
    normalized = auth_service.normalize_username(username)
    if not auth_service.user_exists(normalized):
        raise NotFoundError("User not found")
    return auth_service.load_account_bundle(normalized)


async def parse_body(request: Request, model: Type[BaseModel]) -> BaseModel:
    try:
        payload = await request.json()
    except Exception as exc:
        raise APIValidationError("Invalid JSON body") from exc
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise APIValidationError(str(exc)) from exc
