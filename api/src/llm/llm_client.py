from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional, Sequence

from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_settings
from src.contracts.chat import ConversationMessage
from src.prompts.prompt_templates import AGENT_SYSTEM_PROMPTS, ROUTER_SYSTEM_PROMPT, build_agent_prompt
from src.retrieval.retriever import RetrievedSource, build_context_text, retrieve_sources
from src.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)
MODEL_NAME = settings.gemini_model


@lru_cache(maxsize=1)
def _get_model() -> ChatGoogleGenerativeAI:
    """Create one Gemini client per worker and keep API access server-side."""
    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        google_api_key=settings.gemini_api_key,
        temperature=0.2,
        max_output_tokens=2048,
        max_retries=2,
    )


@dataclass(frozen=True)
class AgentGenerationResult:
    answer: str
    sources: list[RetrievedSource]
    grounding: str


def _content_text(response: Any) -> str:
    """Normalize LangChain/Gemini text blocks into one answer string."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if text:
                    parts.append(str(text))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()
    return str(content or "").strip()


def _build_generation_messages(
    query: str,
    final_prompt: str,
    history: Optional[Sequence[ConversationMessage]] = None,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": final_prompt}]
    for turn in (history or [])[-12:]:
        # History is context only; the system prompt remains authoritative.
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": query})
    return messages


def route_query(query: str) -> str:
    """Classify a query with Gemini into the current response-guidance categories."""
    try:
        response = _get_model().invoke([
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ])
        raw_agent_name = _content_text(response).splitlines()[0]
        agent_name = next(
            (known_name for known_name in AGENT_SYSTEM_PROMPTS if known_name.lower() in raw_agent_name.lower()),
            "General Agent",
        )
        logger.info("Routed query to Gemini guidance mode: %s", agent_name)
        return agent_name
    except Exception as exc:
        logger.error("Gemini routing error: %s", str(exc))
        return "General Agent"


def _generate(
    query: str,
    agent_type: str,
    history: Optional[Sequence[ConversationMessage]],
    document_context: str = "",
    business_context_text: str = "",
    official_context_text: str = "",
    language: str = "en",
) -> str:
    final_prompt = build_agent_prompt(
        agent_type,
        document_context,
        business_context_text=business_context_text,
        official_context_text=official_context_text,
        language=language,
    )
    response = _get_model().invoke(_build_generation_messages(query, final_prompt, history))
    answer = _content_text(response)
    if not answer:
        raise RuntimeError("Gemini returned an empty response.")
    return answer


def agent_generate_with_sources(
    query: str,
    agent_type: str,
    user_id: Optional[str] = None,
    business_id: Optional[str] = None,
    history: Optional[Sequence[ConversationMessage]] = None,
    *,
    sources: Sequence[RetrievedSource] | None = None,
    include_documents: bool = False,
    business_context_text: str = "",
    official_context_text: str = "",
    language: str = "en",
) -> AgentGenerationResult:
    """Generate with Gemini and only the document/business context selected by the caller."""
    selected_sources = list(sources) if sources is not None else []
    if sources is None and include_documents:
        selected_sources = retrieve_sources(query, user_id=user_id, business_id=business_id)

    answer = _generate(
        query,
        agent_type,
        history,
        document_context=build_context_text(selected_sources),
        business_context_text=business_context_text,
        official_context_text=official_context_text,
        language=language,
    )
    grounding = (
        "mixed"
        if selected_sources and official_context_text
        else "document"
        if selected_sources or official_context_text
        else "general"
    )
    return AgentGenerationResult(answer=answer, sources=selected_sources, grounding=grounding)


def generate_from_retrieved_sources(
    query: str,
    agent_type: str,
    sources: Sequence[RetrievedSource],
    history: Optional[Sequence[ConversationMessage]] = None,
    *,
    business_context_text: str = "",
    official_context_text: str = "",
    language: str = "en",
) -> str:
    """Generate from an already scoped retrieval set without querying again."""
    try:
        return _generate(
            query,
            agent_type,
            history,
            document_context=build_context_text(list(sources)),
            business_context_text=business_context_text,
            official_context_text=official_context_text,
            language=language,
        )
    except Exception as exc:
        logger.error("Gemini generation from scoped sources failed: %s", str(exc))
        raise


def stream_agent_with_sources(
    query: str,
    agent_type: str,
    sources: Sequence[RetrievedSource],
    history: Optional[Sequence[ConversationMessage]] = None,
    *,
    business_context_text: str = "",
    official_context_text: str = "",
    language: str = "en",
):
    """Yield Gemini text deltas for callers that need token streaming."""
    final_prompt = build_agent_prompt(
        agent_type,
        build_context_text(list(sources)),
        business_context_text=business_context_text,
        official_context_text=official_context_text,
        language=language,
    )
    stream = _get_model().stream(_build_generation_messages(query, final_prompt, history))
    for chunk in stream:
        delta = _content_text(chunk)
        if delta:
            yield delta


def agent_generate(
    query: str,
    agent_type: str,
    user_id: Optional[str] = None,
    business_id: Optional[str] = None,
    history: Optional[Sequence[ConversationMessage]] = None,
    *,
    include_documents: bool = False,
    business_context_text: str = "",
    official_context_text: str = "",
    language: str = "en",
) -> str:
    """Backward-compatible string-only Gemini generation helper."""
    return agent_generate_with_sources(
        query,
        agent_type,
        user_id=user_id,
        business_id=business_id,
        history=history,
        include_documents=include_documents,
        business_context_text=business_context_text,
        official_context_text=official_context_text,
        language=language,
    ).answer
