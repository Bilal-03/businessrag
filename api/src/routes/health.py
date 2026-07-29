import time
from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Liveness: deliberately does not contact external providers."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check(request: Request):
    """Readiness for this process without turning health checks into cold starts."""
    started_at = getattr(request.app.state, "started_at", None)
    uptime_seconds = round(time.time() - started_at, 1) if started_at else 0
    return {"status": "ready", "uptime_seconds": uptime_seconds}
