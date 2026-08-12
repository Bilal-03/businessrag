from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from config import get_settings
from main import app
from src.integrations import supabase_rest

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
    assert [row["id"] for row in response.json()] == ["obligation-1"]


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
