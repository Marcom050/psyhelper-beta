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


class UserResponse(BaseModel):
    username: str
    metadata: dict[str, Any]
    profile: dict[str, Any]


class AuthResponse(UserResponse):
    authenticated: bool = True
