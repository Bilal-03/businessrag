from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    detected_business_type: Optional[str] = None
    detected_state: Optional[str] = None
    detected_intent: Optional[str] = None
    follow_up_questions: list[str] = []

class BusinessTypeInfo(BaseModel):
    id: str
    label: str
    icon: str
    description: str

class SuggestionResponse(BaseModel):
    suggestions: list[dict]
