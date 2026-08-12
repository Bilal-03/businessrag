from contextlib import asynccontextmanager
import time
import hashlib
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.routes import chat, documents, health, workflow
from src.utils.exceptions import global_exception_handler, http_exception_handler, validation_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError
from src.utils.logger import get_logger
from config import get_settings
from src.utils.rate_limit import rate_limiter

logger = get_logger(__name__)
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Keep startup dependency-free; external services initialize lazily per request."""
    app.state.started_at = time.time()
    app.state.metrics = {
        "requests_total": 0,
        "errors_total": 0,
        "latency_ms_total": 0.0,
        "status_counts": {},
    }
    logger.info("api_started", extra={"event": "api_started"})
    yield
    logger.info("api_stopped", extra={"event": "api_stopped"})

def create_app() -> FastAPI:
    app = FastAPI(title="BizGuide AI API", lifespan=lifespan)
    app.state.started_at = time.time()
    app.state.metrics = {
        "requests_total": 0,
        "errors_total": 0,
        "latency_ms_total": 0.0,
        "status_counts": {},
    }

    # CORS — lock down to actual frontend origin in production
    if settings.environment == "production":
        origins = [settings.frontend_url]
    else:
        origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # Exception handlers
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Request IDs, basic rate limiting, security headers, and structured observability.
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"
        bearer = request.headers.get("Authorization", "")
        token_fingerprint = hashlib.sha256(bearer.encode("utf-8")).hexdigest()[:24] if bearer.startswith("Bearer ") else client_host

        if request.method != "OPTIONS" and path not in {"/health", "/ready", "/metrics"}:
            if path == "/api/documents/upload":
                limit = settings.upload_rate_limit_per_minute
                scope = "upload"
            elif path in {"/api/chat", "/api/chat/stream"}:
                limit = settings.chat_rate_limit_per_minute
                scope = "chat"
            else:
                limit = settings.general_rate_limit_per_minute
                scope = "general"
            allowed, retry_after = rate_limiter.check(scope, token_fingerprint, limit)
            if not allowed:
                logger.warning(
                    "rate_limit_exceeded",
                    extra={
                        "event": "rate_limit_exceeded",
                        "request_id": request_id,
                        "method": request.method,
                        "path": path,
                        "status_code": 429,
                    },
                )
                response = JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests. Please wait and try again.",
                        "code": "rate_limited",
                        "request_id": request_id,
                    },
                    headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(limit)},
                )
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                return response

        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        metrics = getattr(request.app.state, "metrics", None)
        if metrics is not None:
            metrics["requests_total"] += 1
            metrics["latency_ms_total"] += latency_ms
            status_key = str(response.status_code)
            metrics["status_counts"][status_key] = metrics["status_counts"].get(status_key, 0) + 1
            if response.status_code >= 500:
                metrics["errors_total"] += 1
        logger.info(
            "request_completed",
            extra={
                "event": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(latency_ms)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Include routers
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(workflow.router)

    @app.get("/metrics", tags=["health"])
    async def metrics_endpoint(request: Request):
        """Small privacy-safe process metrics endpoint for platform probes."""
        if not settings.metrics_enabled:
            return {"status": "disabled"}
        metrics = request.app.state.metrics
        elapsed = max(0.001, time.time() - request.app.state.started_at)
        return {
            "status": "ok",
            "uptime_seconds": round(elapsed, 1),
            "requests_total": metrics["requests_total"],
            "errors_total": metrics["errors_total"],
            "average_latency_ms": round(metrics["latency_ms_total"] / max(1, metrics["requests_total"]), 1),
            "status_counts": metrics["status_counts"],
        }

    return app

app = create_app()
