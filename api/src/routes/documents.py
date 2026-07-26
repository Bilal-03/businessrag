from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends
from typing import Optional
from config import get_settings
from src.ingestion.loader import load_pdf
from src.chunking.chunker import split_documents
from src.vectordb.vector_store import get_vector_store, clear_namespace, clear_all
from src.utils.logger import get_logger
from langchain_pinecone import PineconeVectorStore
from src.embeddings.embedder import get_embeddings
from src.auth.dependencies import get_current_user

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        # Load and split
        documents = await load_pdf(file)
        chunks = split_documents(documents)

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

        logger.info(f"Successfully uploaded and indexed {len(chunks)} chunks for user {user_id}")
        return {
            "message": f"Successfully uploaded and indexed {len(chunks)} chunks from {file.filename}",
            "session_id": user_id,
        }
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear")
async def clear_documents(user_id: str = Depends(get_current_user)):
    """Delete all vectors for a specific user session."""
    try:
        clear_namespace(user_id)
        logger.info(f"Cleared documents for user {user_id}")
        return {"message": f"All documents cleared for your session.", "session_id": user_id}
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
