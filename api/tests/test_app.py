from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_chat_requires_auth():
    """Protected endpoints must reject unauthenticated requests."""
    response = client.post(
        "/api/chat",
        json={"query": "What is GST?"},
    )
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"

def test_upload_requires_auth():
    """Upload endpoint must reject unauthenticated requests."""
    response = client.post("/api/documents/upload")
    assert response.status_code in (403, 422), f"Expected 403 or 422, got {response.status_code}"
