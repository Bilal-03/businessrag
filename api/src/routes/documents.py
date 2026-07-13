from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import Optional
from config import get_settings
from src.ingestion.loader import load_pdf
from src.chunking.chunker import split_documents
from src.vectordb.vector_store import get_vector_store, clear_namespace, clear_all
from src.utils.logger import get_logger
from langchain_pinecone import PineconeVectorStore
from src.embeddings.embedder import get_embeddings

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    namespace: Optional[str] = Query(None)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    if not namespace:
        raise HTTPException(
            status_code=400,
            detail="A session namespace is required. Please reload the app and try again."
        )

    try:
        # Load and split
        documents = await load_pdf(file)
        chunks = split_documents(documents)

        # Store ONLY in this session's namespace
        PineconeVectorStore.from_documents(
            documents=chunks,
            embedding=get_embeddings(),
            index_name=settings.pinecone_index_name,
            namespace=namespace,
        )

        logger.info(f"Successfully uploaded and indexed {len(chunks)} chunks for namespace {namespace}")
        return {
            "message": f"Successfully uploaded and indexed {len(chunks)} chunks from {file.filename}",
            "namespace": namespace,
        }
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear")
async def clear_documents(namespace: str = Query(...)):
    """Delete all vectors in a specific session namespace."""
    try:
        clear_namespace(namespace)
        logger.info(f"Cleared documents for namespace {namespace}")
        return {"message": f"All documents cleared for your session.", "namespace": namespace}
    except Exception as e:
        logger.error(f"Clear namespace error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear-all")
async def clear_all_documents(secret: str = Query(...)):
    """Admin: clear entire index."""
    if not settings.admin_secret or secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        clear_all()
        logger.warning("Entire knowledge base cleared by admin.")
        return {"message": "Entire knowledge base cleared."}
    except Exception as e:
        logger.error(f"Clear all error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
