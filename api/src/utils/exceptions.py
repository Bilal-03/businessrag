from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)

async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "unhandled_exception",
        exc_info=True,
        extra={"event": "unhandled_exception", "request_id": request_id, "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred. Please try again later.",
            "code": "internal_error",
            "request_id": request_id,
        },
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    detail = exc.detail if isinstance(exc.detail, str) else "Request could not be completed."
    logger.warning(
        "http_error",
        extra={
            "event": "http_error",
            "request_id": request_id,
            "path": request.url.path,
            "status_code": exc.status_code,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "code": "http_error", "request_id": request_id},
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "request_validation_failed",
        extra={"event": "request_validation_failed", "request_id": request_id, "path": request.url.path},
    )
    return JSONResponse(
        status_code=422,
        content={
            "detail": "The request is invalid. Please review the submitted values.",
            "code": "validation_error",
            "request_id": request_id,
        },
    )
