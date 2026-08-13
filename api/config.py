from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

class Settings(BaseSettings):
    groq_api_key: str
    gemini_api_key: str
    pinecone_api_key: str
    pinecone_index_name: str = "bizguide-index"
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: Optional[str] = None
    supabase_jwks_url: Optional[str] = None
    frontend_url: str = "http://localhost:5173"
    environment: str = "development"
    log_level: str = "info"
    max_upload_size_mb: int = 50
    max_upload_pages: int = 100
    max_upload_chunks: int = 1000
    chat_rate_limit_per_minute: int = 30
    upload_rate_limit_per_minute: int = 10
    general_rate_limit_per_minute: int = 120
    redis_url: Optional[str] = None
    metrics_enabled: bool = True
    async_document_ingestion_enabled: bool = False
    document_storage_bucket: str = "documents"
    source_snapshot_storage_bucket: str = "compliance-sources"
    document_worker_poll_seconds: float = 2.0
    document_job_max_attempts: int = 3
    document_job_lease_seconds: int = 900

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def jwt_issuer(self) -> str:
        return self.supabase_jwt_issuer or f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def jwks_url(self) -> str:
        return self.supabase_jwks_url or f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

@lru_cache()
def get_settings():
    return Settings()
