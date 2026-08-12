from fastapi import APIRouter, Form, HTTPException, UploadFile, File, Depends, Request, Query, status
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from config import get_settings
from src.contracts.documents import DocumentRead, DocumentUploadResponse
from src.ingestion.loader import load_pdf
from src.chunking.chunker import split_documents
from src.vectordb.vector_store import clear_document, clear_namespace
from src.utils.logger import get_logger
from langchain_pinecone import PineconeVectorStore
from src.embeddings.embedder import get_embeddings
from src.auth.dependencies import get_current_user
from src.integrations.supabase_rest import SupabaseRestClient, SupabaseRestError

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
            "select": "id,business_id,file_name,mime_type,byte_size,status,created_at,indexed_at",
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
        rows = await _storage(request).request(
            "GET",
            "documents",
            params=params,
        )
        return rows
    except SupabaseRestError as exc:
        raise HTTPException(status_code=503, detail="Document inventory is temporarily unavailable.") from exc


@router.delete("/clear-all", include_in_schema=False)
async def retired_clear_all_route():
    """Keep the retired admin path absent without invoking authentication."""
    raise HTTPException(status_code=404, detail="Not found.")


@router.delete("/clear")
async def clear_documents(request: Request, user_id: str = Depends(get_current_user)):
    """Delete all vectors for a specific user session."""
    try:
        clear_namespace(user_id)
        try:
            await _storage(request).request(
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
        clear_document(user_id, document_id)
        await _storage(request).request(
            "PATCH",
            "documents",
            params={"id": f"eq.{document_id}"},
            payload={"status": "deleted"},
        )
        return {"message": "Document removed.", "request_id": getattr(request.state, "request_id", None)}
    except SupabaseRestError as exc:
        raise HTTPException(status_code=503, detail="The document inventory is temporarily unavailable.") from exc
    except Exception:
        logger.error("document_delete_failed", exc_info=True, extra={"event": "document_delete_failed", "request_id": getattr(request.state, "request_id", None)})
        raise HTTPException(status_code=500, detail="The document could not be removed.")
