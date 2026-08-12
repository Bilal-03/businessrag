import hashlib
from fastapi import APIRouter, Form, Header, HTTPException, UploadFile, File, Depends, Request, Query, status
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from config import get_settings
from src.contracts.documents import DocumentRead, DocumentStatusResponse, DocumentUploadResponse
from src.ingestion.document_jobs import get_document_job_queue
from src.ingestion.loader import load_pdf
from src.chunking.chunker import split_documents
from src.vectordb.vector_store import clear_document, clear_namespace
from src.utils.logger import get_logger
from langchain_pinecone import PineconeVectorStore
from src.embeddings.embedder import get_embeddings
from src.auth.dependencies import get_current_user
from src.integrations.supabase_rest import SupabaseRestClient, SupabaseRestError
from src.integrations.supabase_storage import SupabaseStorageClient

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


def _storage(request: Request) -> SupabaseRestClient:
    token = getattr(request.state, "access_token", None)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication is required.")
    return SupabaseRestClient(token)


def validate_upload_metadata(file: UploadFile) -> None:
    filename = (file.filename or "").strip()
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported.")
    if file.content_type and file.content_type.lower() not in ALLOWED_PDF_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="The uploaded file must be a PDF.")
    if file.size is not None and file.size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PDF files must be {settings.max_upload_size_mb}MB or smaller.",
        )

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    business_id: str | None = Form(default=None, max_length=120),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key", max_length=120),
    user_id: str = Depends(get_current_user),
):
    if settings.async_document_ingestion_enabled:
        return await _enqueue_document(request, file, business_id, idempotency_key, user_id)
    return await _upload_document_sync(request, file, business_id, user_id)


async def _enqueue_document(
    request: Request,
    file: UploadFile,
    business_id: str | None,
    idempotency_key: str | None,
    user_id: str,
):
    """Store the source object and enqueue bounded background work."""
    validate_upload_metadata(file)
    if not settings.supabase_service_role_key:
        raise HTTPException(status_code=503, detail="Async document processing is not configured yet.")
    if business_id:
        try:
            UUID(business_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="The business identifier is invalid.") from exc
    key = (idempotency_key or str(uuid4())).strip()
    if len(key) < 8:
        raise HTTPException(status_code=422, detail="The upload idempotency key is invalid.")

    storage = _storage(request)
    existing_jobs = await storage.request(
        "GET",
        "document_jobs",
        params={
            "select": "id,document_id,status,created_at",
            "owner_id": f"eq.{user_id}",
            "idempotency_key": f"eq.{key}",
            "limit": 1,
        },
    )
    if existing_jobs:
        existing_job = existing_jobs[0]
        existing_document = await _document_row(storage, str(existing_job["document_id"]))
        if existing_document:
            return {
                "message": "This upload is already being processed.",
                "document_id": existing_document["id"],
                "file_name": existing_document["file_name"],
                "chunks_indexed": 0,
                "status": existing_document["status"],
                "job_id": existing_job["id"],
                "created_at": existing_document.get("created_at"),
                "request_id": getattr(request.state, "request_id", None),
            }

    content = await file.read(settings.max_upload_size_bytes + 1)
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PDF files must be {settings.max_upload_size_mb}MB or smaller.",
        )
    if content[:5] != b"%PDF-":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file does not appear to be a valid PDF.")

    safe_file_name = Path((file.filename or "document.pdf").strip()).name[:255] or "document.pdf"
    document_id = str(uuid4())
    job_id = str(uuid4())
    uploaded_at = datetime.now(timezone.utc).isoformat()
    storage_path = f"{user_id}/{document_id}.pdf"
    digest = hashlib.sha256(content).hexdigest()

    try:
        await SupabaseStorageClient(token=getattr(request.state, "access_token", None)).upload(
            storage_path,
            content,
            file.content_type or "application/pdf",
        )
        await storage.request(
            "POST",
            "documents",
            payload={
                "id": document_id,
                "owner_id": user_id,
                "business_id": business_id or None,
                "file_name": safe_file_name,
                "mime_type": file.content_type or "application/pdf",
                "byte_size": len(content),
                "sha256": digest,
                "storage_path": storage_path,
                "status": "uploaded",
                "processing_progress": 0,
                "processing_stage": "queued",
            },
        )
        await storage.request(
            "POST",
            "document_jobs",
            payload={
                "id": job_id,
                "owner_id": user_id,
                "document_id": document_id,
                "idempotency_key": key,
                "status": "queued",
                "max_attempts": settings.document_job_max_attempts,
                "processing_progress": 0,
                "processing_stage": "queued",
            },
        )
        await get_document_job_queue().enqueue(job_id)
    except SupabaseRestError as exc:
        try:
            await SupabaseStorageClient(token=getattr(request.state, "access_token", None)).delete(storage_path)
        except Exception:
            logger.error("document_source_cleanup_failed", exc_info=True, extra={"event": "document_source_cleanup_failed"})
        if exc.status_code == 409:
            existing_jobs = await storage.request(
                "GET",
                "document_jobs",
                params={"select": "id,document_id,status", "owner_id": f"eq.{user_id}", "idempotency_key": f"eq.{key}", "limit": 1},
            )
            if existing_jobs:
                existing_job = existing_jobs[0]
                existing_document = await _document_row(storage, str(existing_job["document_id"]))
                if existing_document:
                    return {
                        "message": "This upload is already being processed.",
                        "document_id": existing_document["id"],
                        "file_name": existing_document["file_name"],
                        "chunks_indexed": 0,
                        "status": existing_document["status"],
                        "job_id": existing_job["id"],
                        "created_at": existing_document.get("created_at"),
                        "request_id": getattr(request.state, "request_id", None),
                    }
        logger.error("document_enqueue_failed", exc_info=True, extra={"event": "document_enqueue_failed"})
        raise HTTPException(status_code=503, detail="The document could not be queued. Please try again.") from exc
    except Exception as exc:
        try:
            await SupabaseStorageClient(token=getattr(request.state, "access_token", None)).delete(storage_path)
        except Exception:
            logger.error("document_source_cleanup_failed", exc_info=True, extra={"event": "document_source_cleanup_failed"})
        logger.error("document_enqueue_failed", exc_info=True, extra={"event": "document_enqueue_failed"})
        raise HTTPException(status_code=503, detail="The document could not be queued. Please try again.") from exc

    return {
        "message": f"{safe_file_name} was uploaded and queued for processing.",
        "document_id": document_id,
        "file_name": safe_file_name,
        "chunks_indexed": 0,
        "status": "queued",
        "job_id": job_id,
        "created_at": uploaded_at,
        "request_id": getattr(request.state, "request_id", None),
    }


async def _document_row(storage: SupabaseRestClient, document_id: str) -> dict | None:
    rows = await storage.request(
        "GET",
        "documents",
        params={
            "select": "id,file_name,status,created_at,processing_progress,processing_stage",
            "id": f"eq.{document_id}",
            "limit": 1,
        },
    )
    return rows[0] if rows else None


async def _upload_document_sync(
    request: Request,
    file: UploadFile = File(...),
    business_id: str | None = Form(default=None, max_length=120),
    user_id: str = Depends(get_current_user),
):
    validate_upload_metadata(file)
    if business_id:
        try:
            UUID(business_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="The business identifier is invalid.") from exc
    safe_file_name = Path((file.filename or "document.pdf").strip()).name[:255] or "document.pdf"
    document_id = str(uuid4())
    uploaded_at = datetime.now(timezone.utc).isoformat()
    storage = _storage(request)
    record_created = False
    vector_indexed = False

    try:
        documents = await load_pdf(
            file,
            max_bytes=settings.max_upload_size_bytes,
            max_pages=settings.max_upload_pages,
        )
        chunks = split_documents(documents)
        if not chunks:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No readable text was found in this PDF.")
        if len(chunks) > settings.max_upload_chunks:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="This PDF is too large to process. Please upload a shorter document.",
            )

        # Create an auditable owner-scoped record before indexing. The vector
        # metadata alone is not a durable document inventory.
        try:
            await storage.request(
                "POST",
                "documents",
                payload={
                    "id": document_id,
                    "owner_id": user_id,
                    "business_id": business_id or None,
                    "file_name": safe_file_name,
                    "mime_type": file.content_type or "application/pdf",
                    "byte_size": file.size,
                    "status": "processing",
                },
            )
            record_created = True
        except SupabaseRestError as exc:
            logger.error(
                "document_record_create_failed",
                exc_info=True,
                extra={"event": "document_record_create_failed", "request_id": getattr(request.state, "request_id", None)},
            )
            raise HTTPException(status_code=503, detail="Document storage is not ready. Please try again later.") from exc

        # Tag chunks with user_id for tenant isolation
        for chunk in chunks:
            if not chunk.metadata:
                chunk.metadata = {}
            chunk.metadata.update({
                "session_id": user_id,
                "document_id": document_id,
                "file_name": safe_file_name,
                "uploaded_at": uploaded_at,
            })
            if business_id:
                chunk.metadata["business_id"] = business_id

        # Store using metadata instead of namespace
        PineconeVectorStore.from_documents(
            documents=chunks,
            embedding=get_embeddings(),
            index_name=settings.pinecone_index_name,
        )
        vector_indexed = True

        try:
            await storage.request(
                "PATCH",
                "documents",
                params={"id": f"eq.{document_id}"},
                payload={"status": "indexed", "indexed_at": datetime.now(timezone.utc).isoformat()},
            )
        except SupabaseRestError:
            # The vector is usable, but the API must not pretend the audit
            # record is current. Surface a retryable state to operators.
            logger.error(
                "document_record_update_failed",
                exc_info=True,
                extra={"event": "document_record_update_failed", "request_id": getattr(request.state, "request_id", None)},
            )
            raise HTTPException(status_code=503, detail="The document was indexed but its audit record is delayed. Please retry shortly.")

        logger.info(
            "document_indexed",
            extra={
                "event": "document_indexed",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        return {
            "message": f"Successfully uploaded and indexed {len(chunks)} chunks from {safe_file_name}",
            "document_id": document_id,
            "file_name": safe_file_name,
            "chunks_indexed": len(chunks),
            "status": "indexed",
            "created_at": uploaded_at,
            "request_id": getattr(request.state, "request_id", None),
        }
    except HTTPException:
        if record_created and not vector_indexed:
            try:
                await storage.request(
                    "PATCH",
                    "documents",
                    params={"id": f"eq.{document_id}"},
                    payload={"status": "failed", "error_code": "processing_rejected"},
                )
            except Exception:
                logger.error("document_failed_status_update", exc_info=True, extra={"event": "document_failed_status_update", "request_id": getattr(request.state, "request_id", None)})
        raise
    except ValueError as exc:
        logger.info(
            "document_upload_rejected",
            extra={
                "event": "document_upload_rejected",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        if record_created and not vector_indexed:
            try:
                await storage.request(
                    "PATCH",
                    "documents",
                    params={"id": f"eq.{document_id}"},
                    payload={"status": "failed", "error_code": "invalid_document"},
                )
            except Exception:
                logger.error("document_failed_status_update", exc_info=True, extra={"event": "document_failed_status_update", "request_id": getattr(request.state, "request_id", None)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        try:
            await storage.request(
                "PATCH",
                "documents",
                params={"id": f"eq.{document_id}"},
                payload={"status": "failed", "error_code": "processing_failed"},
            )
        except Exception:
            logger.error("document_failed_status_update", exc_info=True, extra={"event": "document_failed_status_update", "request_id": getattr(request.state, "request_id", None)})
        logger.error(
            "document_upload_failed",
            exc_info=True,
            extra={
                "event": "document_upload_failed",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        raise HTTPException(status_code=500, detail="We could not process this document. Please try again later.")


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    request: Request,
    business_id: str | None = Query(default=None, max_length=120),
    user_id: str = Depends(get_current_user),
):
    try:
        params = {
            "select": "id,business_id,file_name,mime_type,byte_size,status,created_at,indexed_at,processing_progress,processing_stage,error_message",
            "status": "neq.deleted",
            "order": "created_at.desc",
            "limit": 100,
        }
        if business_id:
            try:
                UUID(business_id)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="The business identifier is invalid.") from exc
            params["business_id"] = f"eq.{business_id}"
        storage = _storage(request)
        try:
            rows = await storage.request("GET", "documents", params=params)
        except SupabaseRestError as exc:
            # Keep the synchronous deployment compatible while migration 0003
            # is being rolled out. The async flag remains off until then.
            if exc.status_code != 400:
                raise
            legacy_params = {**params, "select": "id,business_id,file_name,mime_type,byte_size,status,created_at,indexed_at"}
            rows = await storage.request("GET", "documents", params=legacy_params)
        return rows
    except SupabaseRestError as exc:
        raise HTTPException(status_code=503, detail="Document inventory is temporarily unavailable.") from exc


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def document_status(
    document_id: str,
    request: Request,
    _user_id: str = Depends(get_current_user),
):
    try:
        UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc
    storage = _storage(request)
    try:
        try:
            document_rows = await storage.request(
                "GET",
                "documents",
                params={
                    "select": "id,business_id,file_name,mime_type,byte_size,status,created_at,indexed_at,processing_progress,processing_stage,error_message",
                    "id": f"eq.{document_id}",
                    "limit": 1,
                },
            )
        except SupabaseRestError as exc:
            # A sync deployment can serve status reads before migration 0003.
            if exc.status_code != 400:
                raise
            document_rows = await storage.request(
                "GET",
                "documents",
                params={
                    "select": "id,business_id,file_name,mime_type,byte_size,status,created_at,indexed_at",
                    "id": f"eq.{document_id}",
                    "limit": 1,
                },
            )
            if document_rows:
                document_rows[0].update({"processing_progress": 100 if document_rows[0].get("status") == "indexed" else 0, "processing_stage": "complete" if document_rows[0].get("status") == "indexed" else None, "error_message": None})
        if not document_rows:
            raise HTTPException(status_code=404, detail="Document not found.")
        try:
            job_rows = await storage.request(
                "GET",
                "document_jobs",
                params={
                    "select": "id,document_id,status,attempt_count,max_attempts,processing_progress,processing_stage,last_error,available_at,started_at,completed_at,created_at,updated_at",
                    "document_id": f"eq.{document_id}",
                    "order": "created_at.desc",
                    "limit": 1,
                },
            )
        except SupabaseRestError as exc:
            if exc.status_code == 400:
                job_rows = []
            else:
                raise
        return {"document": document_rows[0], "job": job_rows[0] if job_rows else None}
    except SupabaseRestError as exc:
        raise HTTPException(status_code=503, detail="Document status is temporarily unavailable.") from exc


@router.delete("/clear-all", include_in_schema=False)
async def retired_clear_all_route():
    """Keep the retired admin path absent without invoking authentication."""
    raise HTTPException(status_code=404, detail="Not found.")


@router.delete("/clear")
async def clear_documents(request: Request, user_id: str = Depends(get_current_user)):
    """Delete all vectors for a specific user session."""
    try:
        clear_namespace(user_id)
        storage = _storage(request)
        document_rows = await storage.request(
            "GET",
            "documents",
            params={"select": "id,storage_path", "owner_id": f"eq.{user_id}", "status": "neq.deleted", "limit": 100},
        )
        storage_client = SupabaseStorageClient(token=getattr(request.state, "access_token", None))
        for document in document_rows:
            if document.get("storage_path"):
                await storage_client.delete(document["storage_path"])
        if document_rows and settings.async_document_ingestion_enabled:
            await storage.request(
                "PATCH",
                "document_jobs",
                params={"owner_id": f"eq.{user_id}", "status": "in.(queued,processing)"},
                payload={"status": "failed", "processing_stage": "deleted", "last_error": "The document was deleted."},
            )
        try:
            await storage.request(
                "PATCH",
                "documents",
                params={"owner_id": f"eq.{user_id}", "status": "neq.deleted"},
                payload={"status": "deleted"},
            )
        except SupabaseRestError as exc:
            raise HTTPException(status_code=503, detail="Vectors were cleared, but the document inventory is temporarily unavailable.") from exc
        logger.info(
            "documents_cleared",
            extra={
                "event": "documents_cleared",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        return {"message": "All uploaded documents were cleared.", "request_id": getattr(request.state, "request_id", None)}
    except HTTPException:
        raise
    except Exception:
        logger.error(
            "documents_clear_failed",
            exc_info=True,
            extra={
                "event": "documents_clear_failed",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        raise HTTPException(status_code=500, detail="We could not clear documents. Please try again later.")


@router.delete("/{document_id}")
async def delete_document(document_id: str, request: Request, user_id: str = Depends(get_current_user)):
    try:
        UUID(document_id)
    except ValueError:
        # Keep retired administrative paths unexposed; document IDs are UUIDs.
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        storage = _storage(request)
        document_rows = await storage.request(
            "GET",
            "documents",
            params={"select": "id,storage_path,status", "id": f"eq.{document_id}", "limit": 1},
        )
        if not document_rows:
            raise HTTPException(status_code=404, detail="Document not found.")
        storage_path = document_rows[0].get("storage_path")
        if storage_path:
            await SupabaseStorageClient(token=getattr(request.state, "access_token", None)).delete(storage_path)
        clear_document(user_id, document_id)
        if settings.async_document_ingestion_enabled:
            await storage.request(
                "PATCH",
                "document_jobs",
                params={"document_id": f"eq.{document_id}", "status": "in.(queued,processing)"},
                payload={"status": "failed", "processing_stage": "deleted", "last_error": "The document was deleted."},
            )
        await storage.request(
            "PATCH",
            "documents",
            params={"id": f"eq.{document_id}", "owner_id": f"eq.{user_id}"},
            payload={"status": "deleted", "processing_stage": "deleted", "processing_progress": 100},
        )
        return {"message": "Document removed.", "request_id": getattr(request.state, "request_id", None)}
    except SupabaseRestError as exc:
        raise HTTPException(status_code=503, detail="The document inventory is temporarily unavailable.") from exc
    except Exception:
        logger.error("document_delete_failed", exc_info=True, extra={"event": "document_delete_failed", "request_id": getattr(request.state, "request_id", None)})
        raise HTTPException(status_code=500, detail="The document could not be removed.")
