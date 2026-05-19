"""Authentication API schemas."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    role: str = "client"
    therapist_username: str | None = None
    subscription_status: str = "inactive"
    profile: dict[str, Any] | None = None
    email: str | None = None
    beta_disclaimer_accepted_at: str | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    username: str
    role: str | None = None
    metadata: dict[str, Any]
    profile: dict[str, Any]


class AuthResponse(UserResponse):
    authenticated: bool = True
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
