"""Therapist API schemas."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class TherapistClientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    profile: dict[str, Any] | None = None


class TherapistClientResponse(BaseModel):
    username: str
    metadata: dict[str, Any]
    profile: dict[str, Any]
    wellness: dict[str, Any] | None = None
