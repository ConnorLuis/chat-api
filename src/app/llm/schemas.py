from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = "user"
    content: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="client session id for simple memory")
    messages: List[ChatMessage]
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 256


class ChatResponse(BaseModel):
    trace_id: str
    session_id: Optional[str] = None
    answer: str