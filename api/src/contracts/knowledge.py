from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ReviewerRole = Literal["CA", "CS", "lawyer", "sector_specialist", "bilingual_reviewer", "catalog_admin"]


class AnswerFeedbackCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    conversation_id: str | None = None
    message_id: str | None = None
    rating: Literal["helpful", "not_helpful", "report"]
    reason_code: Literal["incorrect", "outdated", "citation_problem", "applicability_problem", "unsafe", "other"] | None = None
    comments: str | None = Field(default=None, max_length=4000)
    answer_status: Literal["verified", "partially_supported", "general_guidance", "cannot_verify"]
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class SourceDocumentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    authority_name: str = Field(min_length=2, max_length=240)
    jurisdiction: str = Field(min_length=2, max_length=120)
    source_tier: int = Field(ge=1, le=5)
    source_type: Literal["gazette", "statute", "rules", "notification", "circular", "order", "master_direction", "form", "official_guidance", "official_faq", "institutional_guidance"]
    canonical_url: str = Field(pattern=r"^https://", max_length=2048)
    title: str = Field(min_length=2, max_length=500)
    language: Literal["en", "hi", "bilingual"] = "en"
    monitoring_frequency: Literal["daily", "weekly", "monthly", "manual"] = "weekly"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourcePassageCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_version_id: str
    anchor: str = Field(min_length=1, max_length=500)
    heading: str | None = Field(default=None, max_length=500)
    page_number: int | None = Field(default=None, ge=1)
    passage_text: str = Field(min_length=1, max_length=12000)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class SourceVersionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_document_id: str
    version_label: str = Field(min_length=1, max_length=240)
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    retrieved_at: datetime
    last_checked_at: datetime
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    snapshot_path: str = Field(min_length=1, max_length=1000)
    extracted_text: str | None = None
    fetch_status: Literal["healthy", "changed", "unavailable", "error"]


class ClaimCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    claim_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")
    obligation_id: str | None = None
    jurisdiction: str = Field(min_length=2, max_length=120)
    claim_type: Literal["duty", "deadline", "rate", "threshold", "penalty", "eligibility", "definition", "procedure", "exemption"]
    statement_en: str = Field(min_length=1, max_length=4000)
    statement_hi: str | None = Field(default=None, max_length=4000)
    risk_level: Literal["low", "medium", "high", "critical"]
    required_reviewer_role: Literal["CA", "CS", "lawyer", "sector_specialist"]
    required_approvals: int = Field(default=1, ge=1, le=3)
    source_passage_id: str
    applicability_version: int = Field(ge=1)
    applicability_rule: dict[str, Any]
    effective_from: date
    effective_to: date | None = None
    revalidate_by: date


class ReviewDecisionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reviewer_role: Literal["CA", "CS", "lawyer", "sector_specialist", "bilingual_reviewer"]
    decision: Literal["approve", "reject", "request_changes"]
    comments: str = Field(min_length=1, max_length=4000)


class LifecycleTransition(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    lifecycle: Literal["draft", "in_review", "published", "superseded", "quarantined", "rejected"]
    reason: str = Field(min_length=1, max_length=4000)


class SourceVersionTransition(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    review_status: Literal["draft", "in_review", "approved", "superseded", "quarantined"]
    reason: str = Field(min_length=1, max_length=4000)
