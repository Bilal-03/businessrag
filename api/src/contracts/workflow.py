from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Identifier = str
TaskStatus = Literal["todo", "in_progress", "blocked", "done", "dismissed"]
ReviewStatus = Literal["draft", "reviewed", "published"]
IndustryCode = Literal[
    "food_beverage",
    "technology_it",
    "healthcare",
    "education",
    "manufacturing",
    "retail_ecommerce",
    "consulting_services",
    "real_estate",
    "finance",
    "other",
]


def _validate_identifier(value: str | None) -> str | None:
    if value is None:
        return value
    if not value or len(value) > 120 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in value):
        raise ValueError("Identifiers may contain only letters, numbers, hyphens, and underscores.")
    return value


class ObligationRead(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    id: Identifier
    jurisdiction: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    description: str
    source_url: str = Field(min_length=1, max_length=2048)
    source_version: str = Field(min_length=1, max_length=120)
    effective_from: date | None = None
    effective_to: date | None = None
    published: bool = False
    review_status: ReviewStatus = "draft"
    source_citation: str | None = Field(default=None, max_length=2000)
    review_owner: str | None = Field(default=None, max_length=160)
    reviewed_at: datetime | None = None
    applicability_version: int | None = Field(default=None, ge=1)
    applicability_rule: dict[str, Any] | None = None
    metadata: dict = Field(default_factory=dict)


class ComplianceQuestionOption(BaseModel):
    value: str | bool
    label: str


class ComplianceQuestion(BaseModel):
    key: str
    label: str
    description: str
    answer_type: Literal["single_select", "multi_select", "boolean"]
    options: list[ComplianceQuestionOption]
    current_value: Any = None


class CoverageDetail(BaseModel):
    status: Literal["available", "partial", "in_review", "unsupported"]
    message: str
    jurisdiction: str | None = None


class ComplianceCoverage(BaseModel):
    central: CoverageDetail
    state: CoverageDetail


class CompliancePlanResponse(BaseModel):
    business_id: Identifier
    obligations: list[ObligationRead]
    questions: list[ComplianceQuestion]
    coverage: ComplianceCoverage
    profile_version: int = Field(ge=1)


class ComplianceProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_version: Literal[1] | None = None
    regulated_activities: list[str] | None = Field(default=None, max_length=32)
    gst_registration_status: Literal["registered", "not_registered", "not_applicable"] | None = None
    turnover_band: Literal["under_20_lakh", "20_lakh_to_1_crore", "1_to_5_crore", "over_5_crore"] | None = None
    employee_count_band: Literal["0", "1_to_9", "10_to_19", "20_to_49", "50_to_99", "100_plus"] | None = None
    has_physical_establishment: bool | None = None
    operates_multiple_states: bool | None = None
    imports_goods_services: bool | None = None
    exports_goods_services: bool | None = None
    answers: dict[str, str | bool | int | float | list[str] | None] | None = None


class BusinessApplicabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    industry_code: IndustryCode | None = None
    regulated_activities: list[str] | None = Field(default=None, max_length=32)


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    business_id: Identifier = Field(min_length=1, max_length=120)
    obligation_id: Identifier | None = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    status: TaskStatus = "todo"
    due_date: date | None = None

    _business_id = field_validator("business_id")(staticmethod(_validate_identifier))
    _obligation_id = field_validator("obligation_id")(staticmethod(_validate_identifier))


class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: TaskStatus | None = None
    due_date: date | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    id: Identifier
    business_id: Identifier
    obligation_id: Identifier | None = None
    title: str
    status: TaskStatus
    due_date: date | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkflowSummary(BaseModel):
    business_id: Identifier
    obligations_count: int = Field(ge=0)
    tasks_count: int = Field(ge=0)
    tasks_done: int = Field(ge=0)
    source_status: Literal["ready", "empty", "unavailable"]
