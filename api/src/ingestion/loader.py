from langchain_community.document_loaders import PyPDFLoader
import tempfile
import os
from fastapi import UploadFile
from typing import List
from langchain_core.documents import Document

async def load_pdf(file: UploadFile, max_bytes: int, max_pages: int) -> List[Document]:
    """Stream a validated PDF to a temporary file and load bounded page content."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_path = tmp_file.name
            total_bytes = 0
            signature = b""
            while True:
                block = await file.read(64 * 1024)
                if not block:
                    break
                if len(signature) < 5:
                    signature += block[: 5 - len(signature)]
                total_bytes += len(block)
                if total_bytes > max_bytes:
                    raise ValueError(f"PDF files must be {max_bytes // (1024 * 1024)}MB or smaller.")
                tmp_file.write(block)

        if signature != b"%PDF-":
            raise ValueError("The uploaded file does not appear to be a valid PDF.")

        loader = PyPDFLoader(tmp_path)
        documents = loader.load()
        if len(documents) > max_pages:
            raise ValueError(f"PDFs are limited to {max_pages} pages.")
        return documents
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
