import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

class ChatResponse(BaseModel):
    answer: str

client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

# Pinecone & Gemini Setup
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME", "bizguide-index")

if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=3072, # gemini-embedding-2 dimension
        metric='cosine',
        spec=ServerlessSpec(
            cloud='aws',
            region='us-east-1'
        )
    )

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-2", 
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# Initialize vector store for retrieval
vector_store = PineconeVectorStore(
    index_name=index_name,
    embedding=embeddings
)

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

def agent_generate(query: str, agent_type: str) -> str:
    # 1. Retrieve relevant documents from Pinecone
    try:
        docs = vector_store.similarity_search(query, k=4)
        context_text = "\n\n".join([doc.page_content for doc in docs])
    except Exception as e:
        context_text = ""

    system_prompts = {
        "Legal Agent": "You are a Legal & Compliance Subagent for Indian businesses. Focus on MCA, FSSAI, registrations, and legal structures. Be precise, use Markdown, and cite Indian laws.",
        "Tax Agent": "You are a Tax & Finance Subagent for Indian businesses. Focus on GST, Income Tax, Startup India benefits, and funding. Be precise, use Markdown, and cite tax codes.",
        "General Agent": "You are the BizGuide Orchestrator. Provide a comprehensive, well-structured answer to the user's business query using Markdown."
    }
    
    # Default to general if not explicitly matched
    base_prompt = system_prompts.get(agent_type, system_prompts["General Agent"])
    
    # Inject context if available
    if context_text:
        final_prompt = f"{base_prompt}\n\nUse the following extracted context from the user's uploaded business documents to answer their query accurately. If the answer is not in the context, you can rely on your general knowledge.\n\nContext:\n{context_text}"
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
        # Step 1: Routing
        agent_type = route_query(req.query)
        
        # Step 2: Generation by specialized agent
        final_answer = agent_generate(req.query, agent_type)
        
        # Prefix answer to show which agent handled it
        branded_answer = f"**{agent_type} Response:**\n\n" + final_answer
        
        return ChatResponse(answer=branded_answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    try:
        # Save to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(await file.read())
            tmp_path = tmp_file.name

        # Load and parse the PDF
        loader = PyPDFLoader(tmp_path)
        documents = loader.load()

        # Split the text into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)

        # Store in Pinecone
        PineconeVectorStore.from_documents(
            documents=chunks,
            embedding=embeddings,
            index_name=index_name
        )

        # Clean up temp file
        os.unlink(tmp_path)

        return {"message": f"Successfully uploaded and indexed {len(chunks)} chunks from {file.filename}"}
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))
