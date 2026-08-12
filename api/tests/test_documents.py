from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from config import get_settings
from main import app
from src.routes import documents as document_routes


client = TestClient(app)
settings = get_settings()


def auth_headers():
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "test-user-id",
            "aud": settings.supabase_jwt_audience,
            "iss": settings.jwt_issuer,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


class FakeDatabase:
    def __init__(self):
        self.documents = {}
        self.jobs = {}

    async def request(self, method, table, *, params=None, payload=None):
        params = params or {}
        if table == "document_jobs" and method == "GET":
            if "idempotency_key" in params:
                key = params["idempotency_key"].removeprefix("eq.")
                return [job for job in self.jobs.values() if job["idempotency_key"] == key]
            document_id = params.get("document_id", "").removeprefix("eq.")
            return [job for job in self.jobs.values() if not document_id or job["document_id"] == document_id]
        if table == "documents" and method == "GET":
            document_id = params.get("id", "").removeprefix("eq.")
            return [doc for doc in self.documents.values() if not document_id or doc["id"] == document_id]
        if table == "documents" and method == "POST":
            self.documents[payload["id"]] = {
                **payload,
                "created_at": "2026-08-12T10:00:00+00:00",
                "indexed_at": None,
            }
            return [self.documents[payload["id"]]]
        if table == "document_jobs" and method == "POST":
            self.jobs[payload["id"]] = {
                **payload,
                "attempt_count": 0,
                "available_at": "2026-08-12T10:00:00+00:00",
                "created_at": "2026-08-12T10:00:00+00:00",
                "updated_at": "2026-08-12T10:00:00+00:00",
            }
            return [self.jobs[payload["id"]]]
        if method == "PATCH":
            return []
        return []


class FakeStorage:
    uploaded = []
    deleted = []

    def __init__(self, *args, **kwargs):
        pass

    async def upload(self, path, content, content_type="application/pdf"):
        self.uploaded.append((path, content, content_type))

    async def delete(self, path):
        self.deleted.append(path)


class FakeQueue:
    def __init__(self):
        self.job_ids = []

    async def enqueue(self, job_id, delay=0):
        self.job_ids.append((job_id, delay))


def test_async_upload_is_idempotent_and_returns_queued_status(monkeypatch):
    database = FakeDatabase()
    queue = FakeQueue()
    monkeypatch.setattr(document_routes, "_storage", lambda request: database)
    monkeypatch.setattr(document_routes, "SupabaseStorageClient", FakeStorage)
    monkeypatch.setattr(document_routes, "get_document_job_queue", lambda: queue)
    monkeypatch.setattr(document_routes.settings, "async_document_ingestion_enabled", True)
    monkeypatch.setattr(document_routes.settings, "supabase_service_role_key", "service-role-for-test")

    upload_headers = {**auth_headers(), "X-Idempotency-Key": "e2e-upload-key-001"}
    response = client.post(
        "/api/documents/upload",
        headers=upload_headers,
        files={"file": ("notice.pdf", b"%PDF-1.7\nsource text", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["chunks_indexed"] == 0
    assert payload["job_id"] == queue.job_ids[0][0]
    assert len(database.documents) == 1
    assert len(database.jobs) == 1

    duplicate = client.post(
        "/api/documents/upload",
        headers=upload_headers,
        files={"file": ("notice.pdf", b"%PDF-1.7\nsource text", "application/pdf")},
    )

    assert duplicate.status_code == 200
    assert duplicate.json()["document_id"] == payload["document_id"]
    assert len(database.documents) == 1
    assert len(database.jobs) == 1


def test_document_status_returns_document_and_job_progress(monkeypatch):
    class StatusDatabase:
        async def request(self, method, table, *, params=None, payload=None):
            if table == "documents":
                return [{
                    "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "business_id": None,
                    "file_name": "notice.pdf",
                    "mime_type": "application/pdf",
                    "byte_size": 1024,
                    "status": "processing",
                    "created_at": "2026-08-12T10:00:00+00:00",
                    "indexed_at": None,
                    "processing_progress": 45,
                    "processing_stage": "chunking",
                    "error_message": None,
                }]
            return [{
                "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "document_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "status": "processing",
                "attempt_count": 1,
                "max_attempts": 3,
                "processing_progress": 45,
                "processing_stage": "chunking",
                "last_error": None,
                "available_at": None,
                "started_at": "2026-08-12T10:00:00+00:00",
                "completed_at": None,
                "created_at": "2026-08-12T10:00:00+00:00",
                "updated_at": "2026-08-12T10:01:00+00:00",
            }]

    monkeypatch.setattr(document_routes, "_storage", lambda request: StatusDatabase())
    response = client.get(
        "/api/documents/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/status",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.json()["document"]["processing_progress"] == 45
    assert response.json()["job"]["processing_stage"] == "chunking"
