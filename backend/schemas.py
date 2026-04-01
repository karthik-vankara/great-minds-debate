from typing import Any, Literal

from pydantic import BaseModel, Field


class DebateRequest(BaseModel):
    user_input: str = Field(min_length=1)
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    selection_mode: Literal["auto", "manual"] = "auto"
    selected_agents: list[str] = Field(default_factory=list)
    session_name: str | None = None


class DebateEvent(BaseModel):
    node: str
    output: dict[str, Any]


class DebateResponse(BaseModel):
    events: list[DebateEvent]
    result: dict[str, Any]
    chat_history: list[dict[str, Any]]
    saved_session_name: str | None = None


class DebateResumeRequest(BaseModel):
    debate_id: str = Field(min_length=1)
    human_feedback: str = ""
    skip_to_synthesis: bool = False
    user_input: str = Field(min_length=1)
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    session_name: str | None = None


class PersonaPayload(BaseModel):
    display_name: str
    color: str
    tags: list[str]
    system_prompt: str


class PersonaRecord(BaseModel):
    key: str
    origin: Literal["built-in", "custom"]
    data: PersonaPayload


class SessionSaveRequest(BaseModel):
    name: str
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    selection_mode: Literal["auto", "manual"] = "auto"


class SessionLoadResponse(BaseModel):
    name: str
    chat_history: list[dict[str, Any]]
    selection_mode: Literal["auto", "manual"]
    updated_at: str


class SessionSummary(BaseModel):
    name: str
    updated_at: str
    messages: int
    selection_mode: str
