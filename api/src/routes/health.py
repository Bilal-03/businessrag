import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from config import get_settings

router = APIRouter(tags=["health"])
settings = get_settings()

@router.get("/health")
async def health_check():
    """Liveness: deliberately does not contact external providers."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check(request: Request):
    """Readiness for this process without turning health checks into cold starts."""
    if settings.async_document_ingestion_enabled and not settings.supabase_service_role_key:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "Async document ingestion requires a server-only Supabase service-role key.",
            },
        )
    started_at = getattr(request.app.state, "started_at", None)
    uptime_seconds = round(time.time() - started_at, 1) if started_at else 0
    return {"status": "ready", "uptime_seconds": uptime_seconds}
