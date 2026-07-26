from typing import List, Optional
from src.vectordb.vector_store import get_vector_store
from src.utils.logger import get_logger

logger = get_logger(__name__)

def retrieve_context(query: str, user_id: Optional[str] = None, k: int = 4) -> str:
    """Retrieve relevant documents for a query for a specific user."""
    if not user_id:
        return ""
        
    try:
        vs = get_vector_store()
        # Filter by metadata instead of namespace
        docs = vs.similarity_search(query, k=k, filter={"session_id": {"$eq": user_id}})
        context_text = "\n\n".join([doc.page_content for doc in docs])
        return context_text
    except Exception as e:
        logger.error(f"Error retrieving context for user {user_id}: {str(e)}")
        return ""
