import json

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from src.llm.llm_client import agent_generate_with_sources, route_query
from src.contracts.chat import ChatRequest, ChatResponse, SourceCitation
from src.retrieval.retriever import retrieve_sources
from src.llm.llm_client import stream_agent_with_sources
from config import get_settings
from src.utils.logger import get_logger
from src.auth.dependencies import get_current_user

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _citations_for_sources(sources):
    return [
        SourceCitation(
            document_id=source.document_id,
            file_name=source.file_name[:255] if source.file_name else None,
            page_number=source.page_number,
            snippet=" ".join(source.content.split())[:600],
            score=source.score,
        )
        for source in sources
        if source.document_id
    ]


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def chat_stream_endpoint(request: Request, req: ChatRequest, user_id: str = Depends(get_current_user)):
    """Stream answer deltas while keeping retrieval metadata in an initial event."""
    if not settings.groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set in the environment.")

    request_id = getattr(request.state, "request_id", None)
    try:
        agent_type = await run_in_threadpool(route_query, req.query)
        sources = await run_in_threadpool(retrieve_sources, req.query, user_id, req.business_id)
        citations = _citations_for_sources(sources)
        grounding = (
            "document"
            if sources and all(source.document_id for source in sources)
            else "insufficient"
            if sources
            else "general"
        )

        def event_stream():
            yield _sse_event(
                "meta",
                {
                    "agent_type": agent_type,
                    "grounding": grounding,
                    "citations": [citation.model_dump(mode="json") for citation in citations],
                    "request_id": request_id,
                },
            )
            try:
                for token in stream_agent_with_sources(req.query, agent_type, sources, history=req.history):
                    yield _sse_event("token", {"text": token})
                yield _sse_event("done", {})
            except Exception:
                logger.error(
                    "chat_stream_generation_failed",
                    exc_info=True,
                    extra={
                        "event": "chat_stream_generation_failed",
                        "request_id": request_id,
                        "path": request.url.path,
                    },
                )
                yield _sse_event("error", {"detail": "Error generating response", "request_id": request_id})

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Request-ID": request_id or "",
            },
        )
    except Exception:
        logger.error(
            "chat_stream_setup_failed",
            exc_info=True,
            extra={"event": "chat_stream_setup_failed", "request_id": request_id, "path": request.url.path},
        )
        raise HTTPException(status_code=500, detail="Error starting response stream")

@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: Request, req: ChatRequest, user_id: str = Depends(get_current_user)):
    if not settings.groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set in the environment.")

    try:
        agent_type = route_query(req.query)
        result = agent_generate_with_sources(
            req.query,
            agent_type,
            user_id=user_id,
            business_id=req.business_id,
            history=req.history,
        )
        citations = _citations_for_sources(result.sources)
        return ChatResponse(
            answer=result.answer,
            agent_type=agent_type,
            grounding=result.grounding,
            citations=citations,
            request_id=getattr(request.state, "request_id", None),
        )
    except Exception:
        logger.error(
            "chat_generation_failed",
            exc_info=True,
            extra={
                "event": "chat_generation_failed",
                "request_id": getattr(request.state, "request_id", None),
                "path": request.url.path,
            },
        )
        raise HTTPException(status_code=500, detail="Error generating response")
