"""Minimal API exceptions mapped to HTTP responses."""

from starlette import status


class APIError(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "api_error"

    def __init__(self, message: str = "API error"):
        self.message = message
        super().__init__(message)


class AuthenticationError(APIError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_error"


class APIValidationError(APIError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class NotFoundError(APIError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class SubscriptionError(APIError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    code = "subscription_error"
