"""Report API schemas."""

from typing import Any
from pydantic import BaseModel


class WeeklyRecapResponse(BaseModel):
    username: str
    items: list[str]
    text: str


class ClinicalReportResponse(BaseModel):
    username: str
    report: dict[str, Any]
