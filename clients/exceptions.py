"""Exceptions raised by the PsyHelper HTTP API client."""

from __future__ import annotations

from typing import Any


class APIClientError(Exception):
    """Base exception for client-side API boundary failures."""


class APIConnectionError(APIClientError):
    """Raised when the API cannot be reached."""


class APITimeoutError(APIClientError):
    """Raised when the API request times out."""


class APIResponseValidationError(APIClientError):
    """Raised when an API response cannot be parsed into the expected shape."""


class APIHTTPError(APIClientError):
    """Raised for non-success HTTP responses."""

    def __init__(self, status_code: int, message: str, payload: dict[str, Any] | None = None):
        self.status_code = status_code
        self.payload = payload or {}
        super().__init__(message)


class APIUnauthorizedError(APIHTTPError):
    """Raised for HTTP 401 responses."""


class APINotFoundError(APIHTTPError):
    """Raised for HTTP 404 responses."""
