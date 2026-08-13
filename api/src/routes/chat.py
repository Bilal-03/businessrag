import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.auth.dependencies import get_current_user
from src.contracts.chat import ChatRequest, ChatResponse
from src.integrations.supabase_rest import SupabaseRestError
from src.trust.chat_engine import build_chat_response
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _safe_chat_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, SupabaseRestError):
        return HTTPException(status_code=503, detail="The reviewed evidence service is temporarily unavailable.")
    return HTTPException(status_code=500, detail="Error generating response")


def _record_trust_metrics(request: Request, result: ChatResponse) -> None:
    """Record aggregate trust outcomes without retaining prompts or answers."""
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is None:
        return
    evidence_counts = metrics.setdefault("chat_evidence_status_counts", {})
    evidence_counts[result.evidence_status] = evidence_counts.get(result.evidence_status, 0) + 1
    mode_counts = metrics.setdefault("chat_mode_counts", {})
    mode_counts[result.answer_mode] = mode_counts.get(result.answer_mode, 0) + 1
    if result.answer_mode == "reviewed_compliance" and not result.citations:
        metrics["legal_zero_citation_total"] = metrics.get("legal_zero_citation_total", 0) + 1
    if result.evidence_status in {"cannot_verify", "partially_supported"}:
        metrics["verifier_non_verified_total"] = metrics.get("verifier_non_verified_total", 0) + 1


@router.post("/stream")
async def chat_stream_endpoint(request: Request, req: ChatRequest, user_id: str = Depends(get_current_user)):
    """Stream progress only, then reveal one fully assembled trust response.

    Legal and tax prose is never token-streamed before its evidence references
    and applicability checks have passed.
    """
    request_id = getattr(request.state, "request_id", None)
    token = getattr(request.state, "access_token", "")

    async def event_stream():
        yield _sse_event("status", {"stage": "classifying", "message": "Classifying the question"})
        yield _sse_event("status", {"stage": "retrieving", "message": "Checking business-scoped evidence"})
        try:
            result = await build_chat_response(req, user_id, token, request_id)
            _record_trust_metrics(request, result)
            yield _sse_event("status", {"stage": "verifying", "message": "Verifying citations and applicability"})
            yield _sse_event("result", result.model_dump(mode="json"))
            yield _sse_event("done", {})
        except Exception as exc:
            error = _safe_chat_error(exc)
            logger.error(
                "chat_stream_failed",
                exc_info=True,
                extra={"event": "chat_stream_failed", "request_id": request_id, "path": request.url.path},
            )
            yield _sse_event("error", {"detail": error.detail, "request_id": request_id})

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


@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: Request, req: ChatRequest, user_id: str = Depends(get_current_user)):
    try:
        result = await build_chat_response(
            req,
            user_id,
            getattr(request.state, "access_token", ""),
            getattr(request.state, "request_id", None),
        )
        _record_trust_metrics(request, result)
        return result
    except Exception as exc:
        logger.error(
            "chat_generation_failed",
            exc_info=True,
            extra={
                "event": "chat_generation_failed",
                "request_id": getattr(request.state, "request_id", None),
                "path": request.url.path,
            },
        )
        raise _safe_chat_error(exc) from exc
