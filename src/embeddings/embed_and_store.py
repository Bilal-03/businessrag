import json
import os
import shutil
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

# Determine the absolute path to the data directory based on the location of this file
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CHROMA_PERSIST_DIR = os.path.join(BASE_DIR, "data", "chroma_db")

def get_embedding_function():
    """Returns the embedding model specified in the tech stack."""
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def get_vectorstore():
    """Returns the Chroma vectorstore instance."""
    embedding_func = get_embedding_function()
    return Chroma(persist_directory=CHROMA_PERSIST_DIR, embedding_function=embedding_func)

def clear_chroma_db():
    """Removes existing Chroma DB for a clean re-embed."""
    if os.path.exists(CHROMA_PERSIST_DIR):
        shutil.rmtree(CHROMA_PERSIST_DIR)
        print(f"Cleared existing ChromaDB at {CHROMA_PERSIST_DIR}")

def load_and_embed_data(data_file_path: str, clear_existing: bool = True):
    """Loads the comprehensive JSON dataset and embeds it into Chroma."""
    if clear_existing:
        clear_chroma_db()
    
    print(f"Loading data from: {data_file_path}")
    with open(data_file_path, 'r') as f:
        data = json.load(f)
    
    documents = []
    for item in data:
        meta = item["metadata"].copy()
        # Remove filters from database
        meta.pop("business_type", None)
        meta.pop("state", None)
        doc = Document(page_content=item["text"], metadata=meta)
        documents.append(doc)
    
    embedding_func = get_embedding_function()
    
    print(f"Embedding {len(documents)} documents into Chroma DB at {CHROMA_PERSIST_DIR}...")
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embedding_func,
        persist_directory=CHROMA_PERSIST_DIR
    )
    vectorstore.persist()
    print(f"Done! Successfully embedded {len(documents)} chunks into ChromaDB.")
    
    # Quick verification
    test_store = get_vectorstore()
    count = test_store._collection.count()
    print(f"Verification: ChromaDB contains {count} documents.")

if __name__ == "__main__":
    import sys
    
    data_file = os.path.join(BASE_DIR, "data", "processed", "comprehensive_business_data.json")
    
    # Check for --no-clear flag
    clear = "--no-clear" not in sys.argv
    
    if not os.path.exists(data_file):
        print(f"Error: Data file not found at {data_file}")
        sys.exit(1)
    
    load_and_embed_data(data_file, clear_existing=clear)
