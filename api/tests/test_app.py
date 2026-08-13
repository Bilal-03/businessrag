from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from config import get_settings
from main import app
from src.contracts.chat import ChatResponse
from src.routes import chat as chat_routes
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


def test_upload_preflight_allows_idempotency_header():
    response = client.options(
        "/api/documents/upload",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-idempotency-key",
        },
    )
    assert response.status_code == 200
    assert "x-idempotency-key" in response.headers["access-control-allow-headers"].lower()


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


def test_document_inventory_and_clear_are_authenticated():
    assert client.get("/api/documents").status_code == 401
    assert client.delete("/api/documents/clear").status_code == 401


def test_metrics_endpoint_is_privacy_safe():
    response = client.get("/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "query" not in payload
    assert "Authorization" not in response.text


def test_rate_limiter_returns_retry_after_when_limit_is_reached():
    limiter = InMemoryRateLimiter()
    assert limiter.check("chat", "test-user", limit=1) == (True, 0)
    allowed, retry_after = limiter.check("chat", "test-user", limit=1)
    assert allowed is False
    assert retry_after >= 1


def test_chat_stream_emits_progress_verified_result_and_done_event(monkeypatch):
    async def fake_build(*args, **kwargs):
        return ChatResponse(
            answer="Grounded answer from reviewed evidence.",
            answer_mode="reviewed_compliance",
            evidence_status="verified",
            effective_date="2026-08-13",
            agent_type="Legal Agent",
            grounding="document",
        )

    monkeypatch.setattr(chat_routes, "build_chat_response", fake_build)
    response = client.post(
        "/api/chat/stream",
        headers=auth_headers(),
        json={"query": "What does my notice say?"},
    )

    assert response.status_code == 200
    assert "event: status" in response.text
    assert "event: result" in response.text
    assert '"evidence_status": "verified"' in response.text
    assert "Grounded answer from reviewed evidence" in response.text
    assert "event: done" in response.text
