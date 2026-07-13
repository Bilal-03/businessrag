from typing import List, Optional
from src.vectordb.vector_store import get_vector_store
from src.utils.logger import get_logger

logger = get_logger(__name__)

def retrieve_context(query: str, namespace: Optional[str] = None, k: int = 4) -> str:
    """Retrieve relevant documents for a query within a specific namespace."""
    if not namespace:
        return ""
        
    try:
        vs = get_vector_store(namespace)
        docs = vs.similarity_search(query, k=k)
        context_text = "\n\n".join([doc.page_content for doc in docs])
        return context_text
    except Exception as e:
        logger.error(f"Error retrieving context for namespace {namespace}: {str(e)}")
        return ""
