from langchain_community.document_loaders import PyPDFLoader
import tempfile
import os
from fastapi import UploadFile
from typing import List
from langchain_core.documents import Document

async def load_pdf(file: UploadFile) -> List[Document]:
    """Saves an UploadFile to a temporary file and loads it using PyPDFLoader."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(await file.read())
            tmp_path = tmp_file.name

        loader = PyPDFLoader(tmp_path)
        documents = loader.load()
        return documents
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
