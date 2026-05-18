"""Homework API schemas."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class HomeworkAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template: str = Field(min_length=1)
    due_date: str = Field(min_length=1)
    assigned_by: str | None = None
    prompt: str | None = None


class HomeworkSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    assignment_id: str | None = None
    template: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    answer: str = Field(min_length=1)


class HomeworkResponse(BaseModel):
    username: str
    assignments: list[dict[str, Any]]
    submissions: list[dict[str, Any]]
    statuses: list[dict[str, Any]]


class HomeworkAssignmentResponse(BaseModel):
    username: str
    assignment: dict[str, Any]
    wellness: dict[str, Any]


class HomeworkSubmissionResponse(BaseModel):
    username: str
    submission: dict[str, Any]
    wellness: dict[str, Any]
