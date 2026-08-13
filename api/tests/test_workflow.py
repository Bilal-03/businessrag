from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from config import get_settings
from main import app
from src.integrations import supabase_rest
from src.routes import workflow

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


def test_workflow_tasks_require_authentication():
    response = client.get("/api/workflow/tasks", params={"business_id": "biz-1"})
    assert response.status_code == 401


def test_obligations_are_filtered_to_active_jurisdiction(monkeypatch):
    async def fake_request(self, method, table, *, params=None, payload=None):
        assert method == "GET"
        assert table == "obligations"
        assert params["published"] == "eq.true"
        assert params["review_status"] == "eq.published"
        assert params["source_citation"] == "not.is.null"
        assert params["review_owner"] == "not.is.null"
        assert params["reviewed_at"] == "not.is.null"
        return [
            {
                "id": "obligation-1",
                "jurisdiction": "Karnataka",
                "title": "Active filing",
                "description": "Use the current official source.",
                "source_url": "https://example.gov.in/filing",
                "source_version": "2026-01",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "published": True,
                "review_status": "published",
                "source_citation": "Karnataka notice, section 1.",
                "review_owner": "state-review",
                "reviewed_at": "2026-01-01T00:00:00Z",
                "metadata": {},
            },
            {
                "id": "obligation-2",
                "jurisdiction": "Karnataka",
                "title": "Future filing",
                "description": "Not active yet.",
                "source_url": "https://example.gov.in/future",
                "source_version": "2027-01",
                "effective_from": "2027-01-01",
                "effective_to": None,
                "published": True,
                "review_status": "published",
                "source_citation": "Karnataka notice, section 1.",
                "review_owner": "state-review",
                "reviewed_at": "2026-01-01T00:00:00Z",
                "metadata": {},
            },
            {
                "id": "obligation-central",
                "jurisdiction": "India",
                "title": "Central filing",
                "description": "The central source also applies.",
                "source_url": "https://example.gov.in/central",
                "source_version": "2026-central",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "published": True,
                "review_status": "published",
                "source_citation": "Central notice, section 1.",
                "review_owner": "central-review",
                "reviewed_at": "2026-01-01T00:00:00Z",
                "metadata": {},
            },
        ]

    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", fake_request)
    response = client.get(
        "/api/workflow/obligations",
        params={"jurisdiction": "karnataka", "as_of": "2026-08-12"},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == ["obligation-1", "obligation-central"]


def test_obligations_fail_closed_for_unreviewed_or_outdated_rows(monkeypatch):
    async def fake_request(self, method, table, *, params=None, payload=None):
        return [
            {
                "id": "good",
                "jurisdiction": "Karnataka",
                "title": "Current reviewed obligation",
                "description": "Current.",
                "source_url": "https://karnataka.gov.in/notice",
                "source_version": "2026-01",
                "source_citation": "Notice, section 1.",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "published": True,
                "review_status": "published",
                "review_owner": "state-review",
                "reviewed_at": "2026-01-01T00:00:00Z",
                "metadata": {},
            },
            {
                "id": "draft",
                "jurisdiction": "Karnataka",
                "title": "Draft obligation",
                "description": "Not reviewed.",
                "source_url": "https://karnataka.gov.in/draft",
                "source_version": "2026-draft",
                "source_citation": "Draft.",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "published": True,
                "review_status": "draft",
                "review_owner": "state-review",
                "reviewed_at": None,
                "metadata": {},
            },
            {
                "id": "missing-citation",
                "jurisdiction": "Karnataka",
                "title": "Missing citation",
                "description": "Not evidenced.",
                "source_url": "https://karnataka.gov.in/missing",
                "source_version": "2026-missing",
                "source_citation": None,
                "effective_from": "2026-01-01",
                "effective_to": None,
                "published": True,
                "review_status": "published",
                "review_owner": "state-review",
                "reviewed_at": "2026-01-01T00:00:00Z",
                "metadata": {},
            },
            {
                "id": "expired",
                "jurisdiction": "Karnataka",
                "title": "Expired obligation",
                "description": "Outdated.",
                "source_url": "https://karnataka.gov.in/expired",
                "source_version": "2025-expired",
                "source_citation": "Old notice.",
                "effective_from": "2025-01-01",
                "effective_to": "2026-01-01",
                "published": True,
                "review_status": "published",
                "review_owner": "state-review",
                "reviewed_at": "2025-01-01T00:00:00Z",
                "metadata": {},
            },
            {
                "id": "untrusted-source",
                "jurisdiction": "Karnataka",
                "title": "Untrusted source",
                "description": "Not authoritative.",
                "source_url": "https://example.com/notice",
                "source_version": "2026-untrusted",
                "source_citation": "Untrusted notice.",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "published": True,
                "review_status": "published",
                "review_owner": "state-review",
                "reviewed_at": "2026-01-01T00:00:00Z",
                "metadata": {},
            },
        ]

    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", fake_request)
    response = client.get(
        "/api/workflow/obligations",
        params={"jurisdiction": "karnataka", "as_of": "2026-08-12"},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == ["good"]


def test_create_task_is_owner_scoped_and_returns_created_task(monkeypatch):
    captured = {}

    async def fake_request(self, method, table, *, params=None, payload=None):
        captured.update({"method": method, "table": table, "payload": payload})
        return [{
            "id": "task-1",
            "business_id": "biz-1",
            "obligation_id": None,
            "title": "Collect records",
            "status": "todo",
            "due_date": "2026-09-01",
            "completed_at": None,
            "created_at": None,
            "updated_at": None,
        }]

    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", fake_request)
    response = client.post(
        "/api/workflow/tasks",
        headers=auth_headers(),
        json={"business_id": "biz-1", "title": "Collect records", "due_date": "2026-09-01"},
    )

    assert response.status_code == 201
    assert captured["payload"]["owner_id"] == "test-user-id"
    assert response.json()["status"] == "todo"


def test_workflow_storage_failure_is_fail_closed(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise supabase_rest.SupabaseRestError(404)

    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", unavailable)
    response = client.get("/api/workflow/obligations", headers=auth_headers())

    assert response.status_code == 503
    assert "not available yet" in response.json()["detail"]


def test_workflow_schema_read_failure_is_not_exposed_as_client_input_error(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise supabase_rest.SupabaseRestError(400)

    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", unavailable)
    response = client.get(
        "/api/workflow/obligations",
        headers={**auth_headers(), "Origin": "https://businessrag.vercel.app"},
    )

    assert response.status_code == 503
    assert response.headers.get("access-control-allow-origin")


def test_unhandled_workflow_failure_keeps_cors_header(monkeypatch):
    async def explode(*args, **kwargs):
        raise RuntimeError("simulated backend failure")

    monkeypatch.setattr(workflow, "_list_obligation_rows", explode)
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    response = no_raise_client.get(
        "/api/workflow/obligations",
        headers={**auth_headers(), "Origin": "https://businessrag.vercel.app"},
    )

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin")
    assert response.json()["code"] == "internal_error"
