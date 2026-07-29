from contextlib import asynccontextmanager
import time
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.routes import chat, documents, health
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
    logger.info("api_started", extra={"event": "api_started"})
    yield
    logger.info("api_stopped", extra={"event": "api_stopped"})

def create_app() -> FastAPI:
    app = FastAPI(title="BizGuide AI API", lifespan=lifespan)

    # CORS — lock down to actual frontend origin in production
    if settings.environment == "production":
        origins = [settings.frontend_url]
    else:
        origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
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

        if request.method != "OPTIONS" and path not in {"/health", "/ready"}:
            if path == "/api/documents/upload":
                limit = settings.upload_rate_limit_per_minute
                scope = "upload"
            elif path == "/api/chat":
                limit = settings.chat_rate_limit_per_minute
                scope = "chat"
            else:
                limit = settings.general_rate_limit_per_minute
                scope = "general"
            allowed, retry_after = rate_limiter.check(scope, client_host, limit)
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

    return app

app = create_app()
