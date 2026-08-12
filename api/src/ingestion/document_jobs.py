from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any

from config import get_settings
from src.chunking.chunker import split_documents
from src.ingestion.loader import load_pdf
from src.integrations.supabase_rest import SupabaseRestClient, SupabaseRestError
from src.integrations.supabase_storage import SupabaseStorageClient
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

QUEUE_KEY = "bizguide:document-jobs"


class _BytesUpload:
    """Minimal UploadFile-compatible reader for worker-side PDF parsing."""

    def __init__(self, content: bytes, filename: str, content_type: str = "application/pdf"):
        self._stream = BytesIO(content)
        self.filename = filename
        self.content_type = content_type
        self.size = len(content)

    async def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _retry_delay(attempt_count: int) -> float:
    return float(min(15 * 60, 30 * (2 ** max(0, attempt_count - 1))))


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _public_error(exc: Exception) -> tuple[str, str, bool]:
    """Return a stable error code/message and whether the job is permanent."""
    if isinstance(exc, ValueError):
        return "invalid_document", str(exc)[:500], True
    if isinstance(exc, SupabaseRestError):
        if exc.status_code in {400, 404, 409, 422}:
            return "storage_rejected", "The document could not be read from storage.", True
        return "provider_unavailable", "A required document service is temporarily unavailable.", False
    return "processing_failed", "The document could not be indexed. We will retry automatically.", False


async def _get_job(db: SupabaseRestClient, job_id: str) -> dict[str, Any] | None:
    rows = await db.request(
        "GET",
        "document_jobs",
        params={
            "select": "id,document_id,owner_id,status,attempt_count,max_attempts,processing_progress,processing_stage,last_error,available_at,lease_expires_at,started_at,completed_at,created_at,updated_at",
            "id": f"eq.{job_id}",
            "limit": 1,
        },
    )
    return rows[0] if rows else None


async def _get_document(db: SupabaseRestClient, document_id: str) -> dict[str, Any] | None:
    rows = await db.request(
        "GET",
        "documents",
        params={
            "select": "id,owner_id,business_id,file_name,mime_type,byte_size,storage_path,status,created_at,indexed_at",
            "id": f"eq.{document_id}",
            "limit": 1,
        },
    )
    return rows[0] if rows else None


async def _update_job(db: SupabaseRestClient, job_id: str, payload: dict[str, Any], *, status_filter: str | None = None) -> None:
    params = {"id": f"eq.{job_id}"}
    if status_filter:
        params["status"] = f"eq.{status_filter}"
    await db.request("PATCH", "document_jobs", params=params, payload=payload)


async def _update_document(
    db: SupabaseRestClient,
    document_id: str,
    payload: dict[str, Any],
    *,
    exclude_status: str | None = None,
) -> None:
    params = {"id": f"eq.{document_id}"}
    if exclude_status:
        params["status"] = f"neq.{exclude_status}"
    await db.request("PATCH", "documents", params=params, payload=payload)


async def _set_progress(
    db: SupabaseRestClient,
    job_id: str,
    document_id: str,
    progress: int,
    stage: str,
) -> None:
    bounded = max(0, min(100, int(progress)))
    await asyncio.gather(
        _update_job(db, job_id, {"processing_progress": bounded, "processing_stage": stage}, status_filter="processing"),
        _update_document(db, document_id, {"processing_progress": bounded, "processing_stage": stage}, exclude_status="deleted"),
    )


async def process_document_job(job_id: str) -> float | None:
    """Process one queued document and return a retry delay when applicable."""
    db = SupabaseRestClient.admin()
    job = await _get_job(db, job_id)
    if not job or job.get("status") == "indexed":
        return None
    if job.get("status") == "processing":
        lease_expires = _parse_timestamp(job.get("lease_expires_at"))
        if lease_expires and lease_expires > datetime.now(timezone.utc):
            return max(1.0, (lease_expires - datetime.now(timezone.utc)).total_seconds())
        await _update_job(db, job_id, {"status": "queued", "processing_stage": "recovered"}, status_filter="processing")

    available_at = _parse_timestamp(job.get("available_at"))
    if available_at and available_at > datetime.now(timezone.utc):
        return max(1.0, (available_at - datetime.now(timezone.utc)).total_seconds())

    attempt_count = int(job.get("attempt_count") or 0) + 1
    max_attempts = int(job.get("max_attempts") or settings.document_job_max_attempts)
    claimed = await db.request(
        "PATCH",
        "document_jobs",
        params={"id": f"eq.{job_id}", "status": "eq.queued"},
        payload={
            "status": "processing",
            "attempt_count": attempt_count,
            "started_at": _iso_now(),
            "lease_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=settings.document_job_lease_seconds)).isoformat(),
            "processing_stage": "starting",
        },
    )
    if not claimed:
        return None

    document_id = str(job["document_id"])
    try:
        document = await _get_document(db, document_id)
        if not document or document.get("status") == "deleted":
            raise ValueError("The document record no longer exists.")
        storage_path = document.get("storage_path")
        if not storage_path:
            raise ValueError("The document source is unavailable.")

        await _update_document(db, document_id, {"status": "processing", "error_message": None}, exclude_status="deleted")
        await _set_progress(db, job_id, document_id, 10, "downloading")
        content = await SupabaseStorageClient.admin().download(storage_path)
        if not content:
            raise ValueError("The document source is empty.")

        await _set_progress(db, job_id, document_id, 25, "extracting_text")
        upload = _BytesUpload(content, document["file_name"], document.get("mime_type") or "application/pdf")
        documents = await load_pdf(
            upload,
            max_bytes=settings.max_upload_size_bytes,
            max_pages=settings.max_upload_pages,
        )
        if not documents:
            raise ValueError("No readable text was found in this PDF.")

        await _set_progress(db, job_id, document_id, 45, "chunking")
        chunks = split_documents(documents)
        if not chunks:
            raise ValueError("No readable text was found in this PDF.")
        if len(chunks) > settings.max_upload_chunks:
            raise ValueError("This PDF is too large to process. Please upload a shorter document.")

        for chunk in chunks:
            chunk.metadata = chunk.metadata or {}
            chunk.metadata.update({
                "session_id": document["owner_id"],
                "document_id": document_id,
                "file_name": document["file_name"],
                "uploaded_at": document.get("created_at") or _iso_now(),
            })
            if document.get("business_id"):
                chunk.metadata["business_id"] = document["business_id"]

        await _set_progress(db, job_id, document_id, 65, "indexing_vectors")
        from langchain_pinecone import PineconeVectorStore
        from src.embeddings.embedder import get_embeddings

        await asyncio.to_thread(
            PineconeVectorStore.from_documents,
            documents=chunks,
            embedding=get_embeddings(),
            index_name=settings.pinecone_index_name,
            ids=[f"{document_id}:{index}" for index in range(len(chunks))],
        )

        await _set_progress(db, job_id, document_id, 95, "finalizing")
        indexed_at = _iso_now()
        await asyncio.gather(
            _update_document(db, document_id, {
                "status": "indexed",
                "processing_progress": 100,
                "processing_stage": "complete",
                "indexed_at": indexed_at,
                "error_message": None,
            }, exclude_status="deleted"),
            _update_job(db, job_id, {
                "status": "indexed",
                "processing_progress": 100,
                "processing_stage": "complete",
                "completed_at": indexed_at,
                "lease_expires_at": None,
                "last_error": None,
            }, status_filter="processing"),
        )
        logger.info("document_job_indexed", extra={"event": "document_job_indexed", "document_id": document_id, "job_id": job_id})
        return None
    except Exception as exc:
        error_code, message, permanent = _public_error(exc)
        should_retry = not permanent and attempt_count < max_attempts
        if should_retry:
            delay = _retry_delay(attempt_count)
            available_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
            await asyncio.gather(
                _update_document(db, document_id, {
                    "status": "processing",
                    "processing_stage": "retrying",
                    "error_code": error_code,
                    "error_message": message,
                }, exclude_status="deleted"),
                _update_job(db, job_id, {
                    "status": "queued",
                    "processing_stage": "retrying",
                    "available_at": available_at,
                    "lease_expires_at": None,
                    "last_error": message,
                }, status_filter="processing"),
            )
            logger.warning("document_job_retry_scheduled", extra={"event": "document_job_retry_scheduled", "document_id": document_id, "job_id": job_id})
            return delay

        await asyncio.gather(
            _update_document(db, document_id, {
                "status": "failed",
                "processing_stage": "failed",
                "processing_progress": 100,
                "error_code": error_code,
                "error_message": message,
            }, exclude_status="deleted"),
            _update_job(db, job_id, {
                "status": "failed",
                "processing_stage": "failed",
                "lease_expires_at": None,
                "last_error": message,
            }, status_filter="processing"),
        )
        logger.error("document_job_failed", extra={"event": "document_job_failed", "document_id": document_id, "job_id": job_id})
        return None


class DocumentJobQueue:
    """Redis-backed queue with a bounded in-process fallback for development."""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url
        self._redis = None
        self._redis_timeout_error = TimeoutError
        self._memory: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._delayed_tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        if self._worker_task:
            return
        if self.redis_url:
            try:
                import redis.asyncio as redis_asyncio
                from redis import exceptions as redis_exceptions

                # BRPOP is intentionally a blocking read. The socket timeout
                # must exceed the BRPOP poll interval or redis-py cancels the
                # read before Redis can return an ordinary empty result.
                poll_seconds = max(1.0, float(settings.document_worker_poll_seconds))
                self._redis_timeout_error = getattr(redis_exceptions, "TimeoutError", TimeoutError)
                self._redis = redis_asyncio.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=10.0,
                    socket_timeout=max(5.0, poll_seconds + 5.0),
                    health_check_interval=30.0,
                )
                await self._redis.ping()
                logger.info("document_queue_redis_ready", extra={"event": "document_queue_redis_ready"})
            except Exception:
                self._redis = None
                logger.warning("document_queue_redis_unavailable", extra={"event": "document_queue_redis_unavailable"})
        await self._recover_pending_jobs()
        self._stop.clear()
        self._worker_task = asyncio.create_task(self._run(), name="bizguide-document-worker")

    async def _recover_pending_jobs(self) -> None:
        """Re-enqueue jobs left behind by a deploy or worker crash."""
        try:
            rows = await SupabaseRestClient.admin().request(
                "GET",
                "document_jobs",
                params={
                    "select": "id,status,available_at",
                    "status": "in.(queued,processing)",
                    "order": "created_at.asc",
                    "limit": 100,
                },
            )
            for row in rows:
                await self.enqueue(str(row["id"]))
            if rows:
                logger.info("document_jobs_recovered", extra={"event": "document_jobs_recovered"})
        except Exception:
            logger.warning("document_jobs_recovery_unavailable", extra={"event": "document_jobs_recovery_unavailable"})

    async def stop(self) -> None:
        self._stop.set()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        for task in self._delayed_tasks:
            task.cancel()
        self._delayed_tasks.clear()
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def enqueue(self, job_id: str, delay: float = 0) -> None:
        if delay > 0:
            task = asyncio.create_task(self._enqueue_after(job_id, delay))
            self._delayed_tasks.add(task)
            task.add_done_callback(self._delayed_tasks.discard)
            return
        if self._redis is not None:
            await self._redis.rpush(QUEUE_KEY, job_id)
        else:
            await self._memory.put(job_id)

    async def _enqueue_after(self, job_id: str, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            if not self._stop.is_set():
                await self.enqueue(job_id)
        except asyncio.CancelledError:
            pass

    async def _next(self) -> str | None:
        if self._redis is not None:
            try:
                result = await self._redis.brpop(QUEUE_KEY, timeout=max(1, int(settings.document_worker_poll_seconds)))
                return result[1] if result else None
            except (asyncio.TimeoutError, self._redis_timeout_error):
                # A network-level timeout is recoverable. Keep the worker
                # alive and let redis-py establish a fresh connection on the
                # next poll instead of emitting an error every second.
                logger.warning("document_queue_redis_poll_timeout", extra={"event": "document_queue_redis_poll_timeout"})
                return None
        try:
            return await asyncio.wait_for(self._memory.get(), timeout=settings.document_worker_poll_seconds)
        except asyncio.TimeoutError:
            return None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = await self._next()
                if not job_id:
                    continue
                delay = await process_document_job(job_id)
                if delay:
                    await self.enqueue(job_id, delay=delay)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("document_worker_iteration_failed", exc_info=True, extra={"event": "document_worker_iteration_failed"})


_queue: DocumentJobQueue | None = None


def get_document_job_queue() -> DocumentJobQueue:
    global _queue
    if _queue is None:
        _queue = DocumentJobQueue(settings.redis_url)
    return _queue


async def start_document_worker() -> DocumentJobQueue:
    queue = get_document_job_queue()
    await queue.start()
    return queue
