from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Identifier = str
TaskStatus = Literal["todo", "in_progress", "blocked", "done", "dismissed"]
ReviewStatus = Literal["draft", "reviewed", "published"]


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
    metadata: dict = Field(default_factory=dict)


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
