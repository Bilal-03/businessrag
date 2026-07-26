from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from typing import Optional
from config import get_settings
from src.embeddings.embedder import get_embeddings
from src.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Initialize Pinecone client once
pc = Pinecone(api_key=settings.pinecone_api_key)

def init_pinecone_index():
    """Ensure the Pinecone index exists."""
    index_name = settings.pinecone_index_name
    if index_name not in pc.list_indexes().names():
        logger.info(f"Creating Pinecone index: {index_name}")
        pc.create_index(
            name=index_name,
            dimension=3072,  # gemini-embedding-2 dimension
            metric='cosine',
            spec=ServerlessSpec(cloud='aws', region='us-east-1')
        )
    else:
        logger.info(f"Pinecone index '{index_name}' already exists.")

def get_vector_store() -> PineconeVectorStore:
    """Return the vector store."""
    embeddings = get_embeddings()
    kwargs = {
        "index_name": settings.pinecone_index_name,
        "embedding": embeddings
    }
    return PineconeVectorStore(**kwargs)

def clear_namespace(user_id: str):
    """Delete all vectors for a specific user."""
    index = pc.Index(settings.pinecone_index_name)
    # Delete vectors that match this user_id in their metadata
    index.delete(filter={"session_id": {"$eq": user_id}})

def clear_all():
    """Delete all vectors in the index."""
    index = pc.Index(settings.pinecone_index_name)
    index.delete(delete_all=True)
