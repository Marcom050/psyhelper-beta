"""Wellness API schemas preserving the runtime JSON shape."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class MoodEntryRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: str = Field(min_length=1)
    umore: str | None = None
    umore_intensita: int | None = None
    ansia: int | None = None
    stress: int | None = None
    trigger: str | None = None
    sensazioni: Any = None
    pensiero_automatico: str | None = None
    comportamento: str | None = None
    risposta_alternativa: str | None = None
    nota_professionista: str | None = None
    bisogno: str | None = None


class WellnessResponse(BaseModel):
    username: str
    wellness: dict[str, Any]


class MoodEntryResponse(BaseModel):
    username: str
    mood_entry: dict[str, Any]
    wellness: dict[str, Any]
