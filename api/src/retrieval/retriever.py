from dataclasses import dataclass
from typing import List, Optional
from src.vectordb.vector_store import get_vector_store
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetrievedSource:
    """Bounded retrieval result used for prompt context and user citations."""

    content: str
    document_id: str | None
    file_name: str | None
    page_number: int | None
    score: float | None


def _page_number(metadata: dict) -> int | None:
    page = metadata.get("page")
    if isinstance(page, int) and page >= 0:
        return page + 1
    source_page = metadata.get("page_number")
    if isinstance(source_page, int) and source_page > 0:
        return source_page
    return None


def retrieve_sources(
    query: str,
    user_id: Optional[str] = None,
    business_id: Optional[str] = None,
    k: int = 4,
) -> List[RetrievedSource]:
    """Retrieve user-scoped chunks while preserving source metadata."""
    if not user_id:
        return []

    try:
        vs = get_vector_store()
        metadata_filter = {"session_id": {"$eq": user_id}}
        if business_id:
            metadata_filter["business_id"] = {"$eq": business_id}
        try:
            results = vs.similarity_search_with_score(
                query,
                k=k,
                filter=metadata_filter,
            )
        except AttributeError:
            results = [(doc, None) for doc in vs.similarity_search(query, k=k, filter=metadata_filter)]

        sources: list[RetrievedSource] = []
        for doc, score in results:
            metadata = doc.metadata or {}
            content = (doc.page_content or "").strip()
            if not content:
                continue
            sources.append(
                RetrievedSource(
                    content=content,
                    document_id=str(metadata["document_id"]) if metadata.get("document_id") else None,
                    file_name=str(metadata["file_name"]) if metadata.get("file_name") else None,
                    page_number=_page_number(metadata),
                    score=float(score) if isinstance(score, (int, float)) else None,
                )
            )
        return sources
    except Exception as e:
        logger.error(f"Error retrieving context for user {user_id}: {str(e)}")
        return []


def build_context_text(sources: List[RetrievedSource], max_chars: int = 12000) -> str:
    """Format bounded, explicitly untrusted context for the generation prompt."""
    sections: list[str] = []
    remaining = max_chars
    for index, source in enumerate(sources, start=1):
        if remaining <= 0:
            break
        label_parts = [f"source_{index}"]
        if source.file_name:
            label_parts.append(f"file={source.file_name}")
        if source.page_number:
            label_parts.append(f"page={source.page_number}")
        section = f"[{', '.join(label_parts)}]\n{source.content[:remaining]}"
        sections.append(section)
        remaining -= len(section)
    return "\n\n".join(sections)

def retrieve_context(query: str, user_id: Optional[str] = None, k: int = 4) -> str:
    """Retrieve relevant documents for a query for a specific user."""
    return build_context_text(retrieve_sources(query, user_id=user_id, k=k))
