"""Synchronous HTTP client for the PsyHelper FastAPI boundary.

The client intentionally stays thin: it serializes requests, adds the temporary
``X-Username`` header, parses existing API response schemas, and translates
transport/HTTP failures into UI-friendly exceptions. It does not contain CBT,
LLM, Streamlit session, or persistence business logic.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Any, Type, TypeVar
from urllib.parse import quote

from pydantic import BaseModel, ValidationError
import requests

from api.schemas.auth import AuthResponse, UserResponse
from api.schemas.chat import ChatMessageRequest, ChatMessageResponse
from api.schemas.homework import (
    HomeworkAssignmentResponse,
    HomeworkResponse,
    HomeworkSubmissionResponse,
)
from api.schemas.reports import ClinicalReportResponse, WeeklyRecapResponse
from api.schemas.wellness import MoodEntryResponse, WellnessResponse
from clients.exceptions import (
    APIConnectionError,
    APIHTTPError,
    APINotFoundError,
    APIResponseValidationError,
    APITimeoutError,
    APIUnauthorizedError,
)

LOGGER = logging.getLogger(__name__)
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


@dataclass(frozen=True)
class APIClientConfig:
    """Runtime settings for the Streamlit-to-FastAPI HTTP boundary."""

    base_url: str = "http://127.0.0.1:8000"
    timeout_seconds: float = 5.0
    use_http_api: bool = False

    @classmethod
    def from_values(
        cls,
        *,
        base_url: str | None = None,
        timeout_seconds: float | int | str | None = None,
        use_http_api: bool | str | None = None,
    ) -> "APIClientConfig":
        configured_base_url = (
            base_url or os.getenv("API_BASE_URL") or os.getenv("PSYHELPER_API_BASE_URL") or cls.base_url
        )
        configured_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else os.getenv("API_TIMEOUT_SECONDS") or os.getenv("PSYHELPER_API_TIMEOUT_SECONDS")
        )
        configured_use_http = (
            use_http_api
            if use_http_api is not None
            else os.getenv("USE_HTTP_API") or os.getenv("PSYHELPER_USE_HTTP_API")
        )
        return cls(
            base_url=str(configured_base_url).rstrip("/"),
            timeout_seconds=_parse_timeout(configured_timeout),
            use_http_api=_parse_bool(configured_use_http),
        )


def _parse_bool(value: bool | str | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_timeout(value: float | int | str | None) -> float:
    if value is None or value == "":
        return APIClientConfig.timeout_seconds
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        LOGGER.warning("Invalid API timeout %r; using default %.1fs", value, APIClientConfig.timeout_seconds)
        return APIClientConfig.timeout_seconds
    return timeout if timeout > 0 else APIClientConfig.timeout_seconds


class PsyHelperAPIClient:
    """Centralized synchronous API client for the first migrated UI flows."""

    def __init__(
        self,
        config: APIClientConfig | None = None,
        session: requests.Session | None = None,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ):
        self.config = config or APIClientConfig.from_values()
        self.session = session or requests.Session()
        self.access_token = access_token
        self.refresh_token = refresh_token

    def set_auth_tokens(self, access_token: str | None, refresh_token: str | None = None) -> None:
        self.access_token = access_token
        if refresh_token is not None:
            self.refresh_token = refresh_token

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def login(self, username: str, password: str) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "/auth/login",
            json={"username": username, "password": password},
            response_model=AuthResponse,
        )
        self.set_auth_tokens(payload.get("access_token"), payload.get("refresh_token"))
        return payload

    def refresh_access_token(self) -> str:
        if not self.refresh_token:
            raise APIUnauthorizedError(401, "Missing refresh token", {})
        payload = self._request(
            "POST",
            "/auth/refresh",
            json={"refresh_token": self.refresh_token},
            skip_refresh=True,
        )
        access_token = str(payload.get("access_token") or "")
        if not access_token:
            raise APIResponseValidationError("Refresh response missing access token")
        self.access_token = access_token
        return access_token

    def me(self, username: str | None = None) -> dict[str, Any]:
        return self._request("GET", "/me", username=username, response_model=UserResponse)

    def get_wellness(self, username: str) -> dict[str, Any]:
        safe_username = quote(username, safe="")
        response = self._request(
            "GET",
            f"/clients/{safe_username}/wellness",
            username=username,
            response_model=WellnessResponse,
        )
        return response["wellness"]

    def create_mood_entry(self, username: str, mood_entry: dict[str, Any]) -> dict[str, Any]:
        safe_username = quote(username, safe="")
        response = self._request(
            "POST",
            f"/clients/{safe_username}/mood-entries",
            username=username,
            json=mood_entry,
            response_model=MoodEntryResponse,
        )
        return response

    def get_homework(self, username: str) -> dict[str, Any]:
        safe_username = quote(username, safe="")
        return self._request(
            "GET",
            f"/clients/{safe_username}/homework",
            username=username,
            response_model=HomeworkResponse,
        )

    def create_homework_assignment(self, username: str, assignment: dict[str, Any]) -> dict[str, Any]:
        safe_username = quote(username, safe="")
        return self._request(
            "POST",
            f"/clients/{safe_username}/homework-assignments",
            username=username,
            json=assignment,
            response_model=HomeworkAssignmentResponse,
        )

    def create_homework_submission(self, username: str, submission: dict[str, Any]) -> dict[str, Any]:
        payload = {**submission, "username": username}
        return self._request(
            "POST",
            "/homework-submissions",
            username=username,
            json=payload,
            response_model=HomeworkSubmissionResponse,
        )

    def chat_message(
        self,
        username: str,
        user_input: str,
        profile: dict[str, Any],
        wellness: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        payload = ChatMessageRequest(
            username=username,
            user_input=user_input,
            profile=profile,
            wellness=wellness,
            session_id=session_id,
        ).model_dump(exclude_none=True)
        return self._request(
            "POST",
            "/chat/messages",
            username=username,
            json=payload,
            response_model=ChatMessageResponse,
        )

    def get_weekly_recap(self, username: str) -> dict[str, Any]:
        safe_username = quote(username, safe="")
        return self._request(
            "GET",
            f"/clients/{safe_username}/weekly-recap",
            username=username,
            response_model=WeeklyRecapResponse,
        )

    def get_clinical_report(self, username: str) -> dict[str, Any]:
        safe_username = quote(username, safe="")
        return self._request(
            "GET",
            f"/clients/{safe_username}/clinical-report",
            username=username,
            response_model=ClinicalReportResponse,
        )


    def list_my_clients(self) -> dict[str, Any]:
        return self._request("GET", "/therapists/me/clients")

    def create_my_client(self, username: str, password: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"username": username, "password": password}
        if profile is not None:
            payload["profile"] = profile
        return self._request("POST", "/therapists/me/clients", json=payload)

    def get_my_client(self, username: str) -> dict[str, Any]:
        safe_username = quote(username, safe="")
        return self._request("GET", f"/therapists/me/clients/{safe_username}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        username: str | None = None,
        json: dict[str, Any] | None = None,
        response_model: Type[ResponseModel] | None = None,
        skip_refresh: bool = False,
    ) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        elif username:
            headers["X-Username"] = username

        try:
            response = self.session.request(
                method,
                url,
                json=json,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
        except requests.Timeout as exc:
            LOGGER.warning("API request timed out: %s %s", method, url)
            raise APITimeoutError("API request timed out") from exc
        except requests.RequestException as exc:
            LOGGER.warning("API unreachable: %s %s (%s)", method, url, exc)
            raise APIConnectionError("API unreachable") from exc

        if response.status_code == 401 and not skip_refresh and self.refresh_token and path != "/auth/refresh":
            self.refresh_access_token()
            return self._request(method, path, username=username, json=json, response_model=response_model, skip_refresh=True)

        if response.status_code >= 400:
            self._raise_http_error(response)

        try:
            payload = response.json()
        except ValueError as exc:
            LOGGER.warning("API returned invalid JSON: %s %s", method, url)
            raise APIResponseValidationError("Invalid JSON response") from exc

        if response_model is None:
            if not isinstance(payload, dict):
                raise APIResponseValidationError("Expected JSON object response")
            return payload

        try:
            parsed = response_model.model_validate(payload)
        except ValidationError as exc:
            LOGGER.warning("API response validation failed: %s %s (%s)", method, url, exc)
            raise APIResponseValidationError("Invalid API response shape") from exc
        return parsed.model_dump()

    def _raise_http_error(self, response: requests.Response) -> None:
        payload = _response_payload(response)
        message = _error_message(payload) or f"HTTP {response.status_code}"
        LOGGER.warning("API request failed: HTTP %s %s", response.status_code, message)
        if response.status_code in {401, 403}:
            raise APIUnauthorizedError(response.status_code, message, payload)
        if response.status_code == 404:
            raise APINotFoundError(response.status_code, message, payload)
        raise APIHTTPError(response.status_code, message, payload)


def _response_payload(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _error_message(payload: dict[str, Any]) -> str | None:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        return str(message) if message else None
    message = payload.get("message")
    return str(message) if message else None
