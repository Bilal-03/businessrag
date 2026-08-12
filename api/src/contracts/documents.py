from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str
    document_id: str = Field(min_length=1, max_length=120)
    file_name: str = Field(min_length=1, max_length=255)
    chunks_indexed: int = Field(ge=0)
    status: str = Field(default="queued", min_length=1, max_length=32)
    job_id: str | None = Field(default=None, min_length=1, max_length=120)
    created_at: str | None = None
    request_id: str | None = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    id: str = Field(min_length=1, max_length=120)
    business_id: str | None = None
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str = "application/pdf"
    byte_size: int | None = None
    status: str = Field(min_length=1, max_length=32)
    created_at: str | None = None
    indexed_at: str | None = None
    processing_progress: int = Field(default=0, ge=0, le=100)
    processing_stage: str | None = Field(default=None, max_length=80)
    error_message: str | None = Field(default=None, max_length=500)


class DocumentJobRead(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    id: str = Field(min_length=1, max_length=120)
    document_id: str = Field(min_length=1, max_length=120)
    status: str = Field(min_length=1, max_length=32)
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    processing_progress: int = Field(default=0, ge=0, le=100)
    processing_stage: str | None = Field(default=None, max_length=80)
    last_error: str | None = Field(default=None, max_length=500)
    available_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class DocumentStatusResponse(BaseModel):
    document: DocumentRead
    job: DocumentJobRead | None = None
