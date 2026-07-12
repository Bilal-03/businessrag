import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import groq
import tempfile
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

app = FastAPI(title="BizGuide AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str
    namespace: Optional[str] = None   # session-scoped isolation

class ChatResponse(BaseModel):
    answer: str

client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

# Pinecone & Gemini Setup
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME", "bizguide-index")

if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=3072,  # gemini-embedding-2 dimension
        metric='cosine',
        spec=ServerlessSpec(cloud='aws', region='us-east-1')
    )

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-2",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

def get_vector_store(namespace: Optional[str] = None):
    """Return a namespace-scoped vector store. Each session/user is fully isolated."""
    kwargs = {"index_name": index_name, "embedding": embeddings}
    if namespace:
        kwargs["namespace"] = namespace
    return PineconeVectorStore(**kwargs)

def route_query(query: str) -> str:
    """Basic routing logic to simulate multi-agent orchestration."""
    system_prompt = "You are a routing agent. Determine if this query requires 'Legal Agent', 'Tax Agent', or 'General Agent'. Only output the agent name."
    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        temperature=0.1,
        max_tokens=10,
    )
    return res.choices[0].message.content.strip()

def agent_generate(query: str, agent_type: str, namespace: Optional[str] = None) -> str:
    # 1. Retrieve relevant documents — scoped to this session's namespace only
    context_text = ""
    if namespace:
        try:
            vs = get_vector_store(namespace)
            docs = vs.similarity_search(query, k=4)
            context_text = "\n\n".join([doc.page_content for doc in docs])
        except Exception:
            context_text = ""

    system_prompts = {
        "Legal Agent": "You are a Legal & Compliance Subagent for Indian businesses. Focus on MCA, FSSAI, registrations, and legal structures. Be precise, use Markdown, and cite Indian laws.",
        "Tax Agent": "You are a Tax & Finance Subagent for Indian businesses. Focus on GST, Income Tax, Startup India benefits, and funding. Be precise, use Markdown, and cite tax codes.",
        "General Agent": "You are the BizGuide Orchestrator. Provide a comprehensive, well-structured answer to the user's business query using Markdown."
    }

    base_prompt = system_prompts.get(agent_type, system_prompts["General Agent"])

    # Only inject document context if the user has uploaded documents in this session
    if context_text:
        final_prompt = (
            f"{base_prompt}\n\n"
            "Use the following extracted context from the user's uploaded business documents "
            "to answer their query accurately. If the answer is not in the context, rely on your general knowledge.\n\n"
            f"Context:\n{context_text}"
        )
    else:
        final_prompt = base_prompt

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": final_prompt},
            {"role": "user", "content": query}
        ],
        temperature=0.2,
    )
    return res.choices[0].message.content

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set in the environment.")

    try:
        agent_type = route_query(req.query)
        final_answer = agent_generate(req.query, agent_type, namespace=req.namespace)
        branded_answer = f"**{agent_type} Response:**\n\n" + final_answer
        return ChatResponse(answer=branded_answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/documents/upload")
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
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(await file.read())
            tmp_path = tmp_file.name

        loader = PyPDFLoader(tmp_path)
        documents = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)

        # Store ONLY in this session's namespace — completely isolated from other users
        PineconeVectorStore.from_documents(
            documents=chunks,
            embedding=embeddings,
            index_name=index_name,
            namespace=namespace,
        )

        os.unlink(tmp_path)
        return {
            "message": f"Successfully uploaded and indexed {len(chunks)} chunks from {file.name}",
            "namespace": namespace,
        }
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/documents/clear")
async def clear_documents(namespace: str = Query(...)):
    """Delete all vectors in a specific session namespace. Keeps other users unaffected."""
    try:
        index = pc.Index(index_name)
        index.delete(delete_all=True, namespace=namespace)
        return {"message": f"All documents cleared for your session.", "namespace": namespace}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/documents/clear-all")
async def clear_all_documents(secret: str = Query(...)):
    """Admin: clear entire index. Requires ADMIN_SECRET env var."""
    admin_secret = os.getenv("ADMIN_SECRET", "")
    if not admin_secret or secret != admin_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        index = pc.Index(index_name)
        index.delete(delete_all=True)
        return {"message": "Entire knowledge base cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
