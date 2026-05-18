"""Chat API schemas."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    profile: dict[str, Any]
    wellness: dict[str, Any]
    session_id: str | None = None


class ChatMessageResponse(BaseModel):
    username: str
    content: str
