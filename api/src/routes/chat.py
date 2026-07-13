from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.llm.llm_client import route_query, agent_generate
from config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    query: str
    namespace: Optional[str] = None   # session-scoped isolation

class ChatResponse(BaseModel):
    answer: str

@router.post("", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if not settings.groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set in the environment.")

    try:
        agent_type = route_query(req.query)
        final_answer = agent_generate(req.query, agent_type, namespace=req.namespace)
        branded_answer = f"**{agent_type} Response:**\n\n" + final_answer
        return ChatResponse(answer=branded_answer)
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating response")
