from pydantic_settings import BaseSettings
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
    admin_secret: Optional[str] = None
    environment: str = "development"
    log_level: str = "info"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()
