from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str
    document_id: str = Field(min_length=1, max_length=120)
    file_name: str = Field(min_length=1, max_length=255)
    chunks_indexed: int = Field(ge=1)
    status: str = Field(default="indexed", min_length=1, max_length=32)
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
