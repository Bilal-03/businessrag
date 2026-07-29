from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request, status
from config import get_settings
from src.ingestion.loader import load_pdf
from src.chunking.chunker import split_documents
from src.vectordb.vector_store import clear_namespace
from src.utils.logger import get_logger
from langchain_pinecone import PineconeVectorStore
from src.embeddings.embedder import get_embeddings
from src.auth.dependencies import get_current_user

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


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

@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    validate_upload_metadata(file)

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

        # Tag chunks with user_id for tenant isolation
        for chunk in chunks:
            if not chunk.metadata:
                chunk.metadata = {}
            chunk.metadata["session_id"] = user_id

        # Store using metadata instead of namespace
        PineconeVectorStore.from_documents(
            documents=chunks,
            embedding=get_embeddings(),
            index_name=settings.pinecone_index_name,
        )

        logger.info(
            "document_indexed",
            extra={
                "event": "document_indexed",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        return {
            "message": f"Successfully uploaded and indexed {len(chunks)} chunks from {file.filename}",
            "chunks_indexed": len(chunks),
            "request_id": getattr(request.state, "request_id", None),
        }
    except HTTPException:
        raise
    except ValueError as exc:
        logger.info(
            "document_upload_rejected",
            extra={
                "event": "document_upload_rejected",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        logger.error(
            "document_upload_failed",
            exc_info=True,
            extra={
                "event": "document_upload_failed",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        raise HTTPException(status_code=500, detail="We could not process this document. Please try again later.")

@router.delete("/clear")
async def clear_documents(request: Request, user_id: str = Depends(get_current_user)):
    """Delete all vectors for a specific user session."""
    try:
        clear_namespace(user_id)
        logger.info(
            "documents_cleared",
            extra={
                "event": "documents_cleared",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        return {"message": "All uploaded documents were cleared.", "request_id": getattr(request.state, "request_id", None)}
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
