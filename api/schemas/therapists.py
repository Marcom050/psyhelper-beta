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


class TherapistDashboardResponse(BaseModel):
    tenant: dict[str, Any]
    subscription: dict[str, Any]
    stats: dict[str, Any]


class TherapistClientSnapshotResponse(BaseModel):
    profile: dict[str, Any]
    metadata: dict[str, Any]
    wellness_summary: dict[str, Any]
    homework_summary: dict[str, Any]
    recent_mood_trends: list[dict[str, Any]]
