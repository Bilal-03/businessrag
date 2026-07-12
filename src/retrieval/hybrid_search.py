from src.embeddings.embed_and_store import get_vectorstore

def search_documents(query: str, k: int = 6):
    """
    Performs vector search on ChromaDB.
    """
    vectorstore = get_vectorstore()
    
    # Pure semantic search
    docs = vectorstore.similarity_search(query, k=k)
    return docs

def format_docs(docs):
    """Formats retrieved documents into a single context string with rich metadata."""
    formatted = []
    for d in docs:
        authority = d.metadata.get('authority', 'Unknown')
        biz_type = d.metadata.get('business_type', 'general')
        state = d.metadata.get('state', 'national')
        doc_type = d.metadata.get('doc_type', 'general')
        formatted.append(
            f"[Source: {authority} | Type: {biz_type} | State: {state} | Category: {doc_type}]\n{d.page_content}"
        )
    return "\n\n".join(formatted)
