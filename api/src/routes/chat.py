from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from src.llm.llm_client import route_query, agent_generate
from config import get_settings
from src.utils.logger import get_logger
from src.auth.dependencies import get_current_user

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=8000)

class ChatResponse(BaseModel):
    answer: str
    request_id: str | None = None

@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: Request, req: ChatRequest, user_id: str = Depends(get_current_user)):
    if not settings.groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set in the environment.")

    try:
        agent_type = route_query(req.query)
        final_answer = agent_generate(req.query, agent_type, user_id=user_id)
        return ChatResponse(answer=final_answer, request_id=getattr(request.state, "request_id", None))
    except Exception:
        logger.error(
            "chat_generation_failed",
            exc_info=True,
            extra={
                "event": "chat_generation_failed",
                "request_id": getattr(request.state, "request_id", None),
                "path": request.url.path,
            },
        )
        raise HTTPException(status_code=500, detail="Error generating response")
