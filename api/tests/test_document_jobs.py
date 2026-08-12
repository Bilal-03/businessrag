import asyncio

from langchain_core.documents import Document

from src.ingestion import document_jobs
from src.integrations.supabase_rest import SupabaseRestError


JOB_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
DOCUMENT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def base_job():
    return {
        "id": JOB_ID,
        "document_id": DOCUMENT_ID,
        "owner_id": "test-user-id",
        "status": "queued",
        "attempt_count": 0,
        "max_attempts": 3,
        "processing_progress": 0,
        "processing_stage": "queued",
        "last_error": None,
        "available_at": "2020-01-01T00:00:00+00:00",
        "lease_expires_at": None,
        "started_at": None,
        "completed_at": None,
        "created_at": "2026-08-12T10:00:00+00:00",
        "updated_at": "2026-08-12T10:00:00+00:00",
    }


def base_document():
    return {
        "id": DOCUMENT_ID,
        "owner_id": "test-user-id",
        "business_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "file_name": "notice.pdf",
        "mime_type": "application/pdf",
        "byte_size": 1024,
        "storage_path": "test-user-id/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa.pdf",
        "status": "uploaded",
        "created_at": "2026-08-12T10:00:00+00:00",
        "indexed_at": None,
    }


class FakeDatabase:
    def __init__(self):
        self.job = base_job()
        self.document = base_document()

    async def request(self, method, table, *, params=None, payload=None):
        params = params or {}
        if method == "GET" and table == "document_jobs":
            return [self.job]
        if method == "GET" and table == "documents":
            return [self.document]
        if method == "PATCH" and table == "document_jobs":
            required_status = params.get("status", "").removeprefix("eq.")
            if required_status and self.job["status"] != required_status:
                return []
            self.job.update(payload or {})
            return [self.job]
        if method == "PATCH" and table == "documents":
            self.document.update(payload or {})
            return [self.document]
        return []


class SuccessfulStorage:
    async def download(self, path):
        return b"%PDF-1.7\nsource text"


class FailingStorage:
    async def download(self, path):
        raise SupabaseRestError(503)


def test_document_job_indexes_with_deterministic_vector_ids(monkeypatch):
    database = FakeDatabase()
    captured = {}

    monkeypatch.setattr(document_jobs.SupabaseRestClient, "admin", lambda: database)
    monkeypatch.setattr(document_jobs.SupabaseStorageClient, "admin", lambda: SuccessfulStorage())
    async def fake_load_pdf(*args, **kwargs):
        return [Document(page_content="source text", metadata={})]

    monkeypatch.setattr(document_jobs, "load_pdf", fake_load_pdf)
    monkeypatch.setattr(document_jobs, "split_documents", lambda docs: docs)

    class FakeVectorStore:
        @classmethod
        def from_documents(cls, **kwargs):
            captured.update(kwargs)
            return cls()

    import langchain_pinecone

    monkeypatch.setattr(langchain_pinecone, "PineconeVectorStore", FakeVectorStore)
    monkeypatch.setattr("src.embeddings.embedder.get_embeddings", lambda: "test-embedding")

    result = asyncio.run(document_jobs.process_document_job(JOB_ID))

    assert result is None
    assert database.job["status"] == "indexed"
    assert database.document["status"] == "indexed"
    assert captured["ids"] == [f"{DOCUMENT_ID}:0"]
    assert captured["documents"][0].metadata["business_id"] == database.document["business_id"]


def test_document_job_requeues_transient_provider_failure(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(document_jobs.SupabaseRestClient, "admin", lambda: database)
    monkeypatch.setattr(document_jobs.SupabaseStorageClient, "admin", lambda: FailingStorage())

    delay = asyncio.run(document_jobs.process_document_job(JOB_ID))

    assert delay == 30.0
    assert database.job["status"] == "queued"
    assert database.job["attempt_count"] == 1
    assert database.job["processing_stage"] == "retrying"
    assert database.document["status"] == "processing"
