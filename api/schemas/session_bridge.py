"""Request and response shapes for Session Bridge persistence."""

from typing import Annotated

from pydantic import BaseModel, Field


WeekRating = Annotated[int, Field(strict=True, ge=1, le=5)]


class SessionBridgeRequest(BaseModel):
    selected_refs: list[str]
    priority_ref: str | None
    optional_text: str = ""
    week_rating: WeekRating | None = None


class SessionBridgeResponse(BaseModel):
    username: str
    session_bridge: dict
