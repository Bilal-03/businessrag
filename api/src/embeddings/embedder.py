from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config import get_settings

settings = get_settings()

def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Returns the Gemini embeddings model instance."""
    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-2",
        google_api_key=settings.gemini_api_key
    )
