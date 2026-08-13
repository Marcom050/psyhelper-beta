"""Request and response shapes for Session Bridge persistence."""

from pydantic import BaseModel


class SessionBridgeRequest(BaseModel):
    selected_refs: list[str]
    priority_ref: str | None
    optional_text: str = ""


class SessionBridgeResponse(BaseModel):
    username: str
    session_bridge: dict
