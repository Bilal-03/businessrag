from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationMessage(BaseModel):
    """A user-visible turn supplied as optional conversation context."""

    model_config = ConfigDict(str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


class ChatRequest(BaseModel):
    """Backward-compatible chat request with scoped context identifiers."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=120)
    business_id: str | None = Field(default=None, max_length=120)
    history: list[ConversationMessage] = Field(default_factory=list, max_length=20)


class SourceCitation(BaseModel):
    """A safe, bounded reference returned with a grounded answer."""

    model_config = ConfigDict(str_strip_whitespace=True)

    document_id: str = Field(min_length=1, max_length=120)
    file_name: str | None = Field(default=None, max_length=255)
    page_number: int | None = Field(default=None, ge=1)
    snippet: str = Field(min_length=1, max_length=600)
    score: float | None = Field(default=None, ge=-1, le=1)


class ChatResponse(BaseModel):
    answer: str
    agent_type: str = "General Agent"
    grounding: Literal["document", "mixed", "general", "insufficient"] = "general"
    citations: list[SourceCitation] = Field(default_factory=list, max_length=8)
    request_id: str | None = None
