from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class PostConsultationOnboardingCreateRequest(BaseModel):
    patient_id: str = Field(min_length=1)


class PostConsultationBaselineRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


class PostConsultationGoalsRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


class PostConsultationDiaryRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


class PostConsultationCBTEntryRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


class PostConsultationNextSessionNoteRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


class PostConsultationOnboardingResponse(BaseModel):
    onboarding: dict[str, Any]
    status: str
    progress: dict[str, int]
    expires_at: str | None = None


class PostConsultationSummaryResponse(BaseModel):
    onboarding_id: str
    summary: dict[str, Any]
