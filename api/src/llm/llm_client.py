import groq
from dataclasses import dataclass
from typing import Optional, Sequence
from config import get_settings
from src.contracts.chat import ConversationMessage
from src.retrieval.retriever import RetrievedSource, build_context_text, retrieve_sources
from src.prompts.prompt_templates import AGENT_SYSTEM_PROMPTS, ROUTER_SYSTEM_PROMPT, build_agent_prompt
from src.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Initialize Groq client
client = groq.Groq(api_key=settings.groq_api_key)
MODEL_NAME = "llama-3.3-70b-versatile"


@dataclass(frozen=True)
class AgentGenerationResult:
    answer: str
    sources: list[RetrievedSource]
    grounding: str


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
    """Classify a query into the current response-guidance categories."""
    try:
        res = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            temperature=0.1,
            max_tokens=10,
        )
        raw_agent_name = res.choices[0].message.content.strip().splitlines()[0]
        agent_name = next(
            (known_name for known_name in AGENT_SYSTEM_PROMPTS if known_name.lower() in raw_agent_name.lower()),
            "General Agent",
        )
        logger.info(f"Routed query to: {agent_name}")
        return agent_name
    except Exception as e:
        logger.error(f"Routing error: {str(e)}")
        return "General Agent"

def agent_generate_with_sources(
    query: str,
    agent_type: str,
    user_id: Optional[str] = None,
    business_id: Optional[str] = None,
    history: Optional[Sequence[ConversationMessage]] = None,
) -> AgentGenerationResult:
    """Generate a response and retain the retrieval evidence for the API layer."""
    sources = retrieve_sources(query, user_id=user_id, business_id=business_id)
    context_text = build_context_text(sources)
    final_prompt = build_agent_prompt(agent_type, context_text)

    try:
        res = client.chat.completions.create(
            model=MODEL_NAME,
            messages=_build_generation_messages(query, final_prompt, history),
            temperature=0.2,
        )
        grounding = (
            "document"
            if sources and all(source.document_id for source in sources)
            else "insufficient"
            if sources
            else "general"
        )
        return AgentGenerationResult(
            answer=res.choices[0].message.content,
            sources=sources,
            grounding=grounding,
        )
    except Exception as e:
        logger.error(f"Generation error with {agent_type}: {str(e)}")
        raise


def stream_agent_with_sources(
    query: str,
    agent_type: str,
    sources: Sequence[RetrievedSource],
    history: Optional[Sequence[ConversationMessage]] = None,
):
    """Yield model text deltas for the SSE endpoint."""
    final_prompt = build_agent_prompt(agent_type, build_context_text(list(sources)))
    stream = client.chat.completions.create(
        model=MODEL_NAME,
        messages=_build_generation_messages(query, final_prompt, history),
        temperature=0.2,
        stream=True,
    )
    for chunk in stream:
        delta = getattr(chunk.choices[0].delta, "content", None) if chunk.choices else None
        if delta:
            yield delta


def agent_generate(
    query: str,
    agent_type: str,
    user_id: Optional[str] = None,
    business_id: Optional[str] = None,
    history: Optional[Sequence[ConversationMessage]] = None,
) -> str:
    """Backward-compatible string-only generation helper."""
    return agent_generate_with_sources(
        query,
        agent_type,
        user_id=user_id,
        business_id=business_id,
        history=history,
    ).answer
