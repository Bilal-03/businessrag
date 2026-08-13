from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationMessage(BaseModel):
    """A user-visible turn supplied as optional conversation context."""

    model_config = ConfigDict(str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


class ChatRequest(BaseModel):
    """Versioned, business-scoped chat request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=120)
    business_id: str | None = Field(default=None, max_length=120)
    language: Literal["en", "hi"] = "en"
    as_of: date | None = None
    history: list[ConversationMessage] = Field(default_factory=list, max_length=20)


class SourceCitation(BaseModel):
    """One official or private-document evidence reference."""

    model_config = ConfigDict(str_strip_whitespace=True)

    evidence_id: str | None = Field(default=None, max_length=120)
    source_kind: Literal["official", "user_document"] = "user_document"
    document_id: str | None = Field(default=None, max_length=120)
    source_id: str | None = Field(default=None, max_length=120)
    source_version_id: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=500)
    authority: str | None = Field(default=None, max_length=240)
    url: str | None = Field(default=None, max_length=2048)
    anchor: str | None = Field(default=None, max_length=500)
    file_name: str | None = Field(default=None, max_length=255)
    page_number: int | None = Field(default=None, ge=1)
    snippet: str = Field(min_length=1, max_length=1200)
    score: float | None = Field(default=None, ge=-1, le=1)
    source_tier: int | None = Field(default=None, ge=1, le=5)
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    last_checked_at: datetime | None = None
    content_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    reviewed_at: datetime | None = None
    approval_count: int | None = Field(default=None, ge=1)
    reviewer_roles: list[str] = Field(default_factory=list, max_length=8)


class VerifiedClaim(BaseModel):
    claim_id: str
    statement: str
    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    applicability: list[str] = Field(default_factory=list, max_length=12)
    risk_level: Literal["low", "medium", "high", "critical"]
    claim_type: Literal["duty", "deadline", "rate", "threshold", "penalty", "eligibility", "definition", "procedure", "exemption"] | None = None
    language_status: Literal["reviewed", "generated_explanation", "english_only"] = "reviewed"
    statutory_text_en: str
    explanation_hi: str | None = None


class EscalationGuidance(BaseModel):
    recommended_role: Literal["CA", "CS", "lawyer", "sector_specialist"]
    reason: str
    briefing: list[str] = Field(default_factory=list, max_length=12)


class ChatResponse(BaseModel):
    schema_version: Literal[2] = 2
    answer: str
    answer_mode: Literal[
        "reviewed_compliance",
        "user_document_analysis",
        "general_business_guidance",
        "professional_escalation",
    ]
    evidence_status: Literal["verified", "partially_supported", "general_guidance", "cannot_verify"]
    language: Literal["en", "hi"] = "en"
    claims: list[VerifiedClaim] = Field(default_factory=list, max_length=20)
    citations: list[SourceCitation] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    missing_inputs: list[str] = Field(default_factory=list, max_length=20)
    conflicts: list[str] = Field(default_factory=list, max_length=20)
    coverage: dict[str, Any] = Field(default_factory=dict)
    effective_date: date
    profile_version: int | None = Field(default=None, ge=1)
    escalation: EscalationGuidance | None = None
    request_id: str | None = None

    # Compatibility fields retained while persisted conversations and older
    # clients migrate to the v2 trust contract.
    agent_type: str = "General Agent"
    grounding: Literal["document", "mixed", "general", "insufficient"] = "general"
