from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from config import get_settings
from main import app
from src.utils.rate_limit import InMemoryRateLimiter

client = TestClient(app)
settings = get_settings()


def auth_headers(*, audience=None, expires_in_minutes=5):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "test-user-id",
            "aud": audience or settings.supabase_jwt_audience,
            "iss": settings.jwt_issuer,
            "iat": now,
            "exp": now + timedelta(minutes=expires_in_minutes),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_readiness_check():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

def test_chat_requires_auth():
    """Protected endpoints must reject unauthenticated requests."""
    response = client.post(
        "/api/chat",
        json={"query": "What is GST?"},
    )
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]

def test_upload_requires_auth():
    """Upload endpoint must reject unauthenticated requests."""
    response = client.post("/api/documents/upload")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"


def test_chat_rejects_token_with_wrong_audience():
    response = client.post(
        "/api/chat",
        headers=auth_headers(audience="wrong-audience"),
        json={"query": "What is GST?"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials."


def test_chat_rejects_oversized_query_with_safe_error_shape():
    response = client.post(
        "/api/chat",
        headers=auth_headers(),
        json={"query": "x" * 8001},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_upload_rejects_non_pdf_before_processing():
    response = client.post(
        "/api/documents/upload",
        headers=auth_headers(),
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are supported."


def test_upload_rejects_invalid_pdf_signature():
    response = client.post(
        "/api/documents/upload",
        headers=auth_headers(),
        files={"file": ("document.PDF", b"not a PDF", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "The uploaded file does not appear to be a valid PDF."


def test_legacy_admin_clear_all_route_is_not_exposed():
    response = client.delete("/api/documents/clear-all?secret=not-used")
    assert response.status_code == 404


def test_rate_limiter_returns_retry_after_when_limit_is_reached():
    limiter = InMemoryRateLimiter()
    assert limiter.check("chat", "test-user", limit=1) == (True, 0)
    allowed, retry_after = limiter.check("chat", "test-user", limit=1)
    assert allowed is False
    assert retry_after >= 1
