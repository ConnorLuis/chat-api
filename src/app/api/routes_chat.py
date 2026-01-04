import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.app.core.logging import get_trace_id
from src.app.llm.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: Request, body: ChatRequest):
    trace_id = get_trace_id(req)

    last_user = ""
    for m in reversed(body.messages):
        if m.role == "user":
            last_user = m.content
            break

    answer = f"[mock] you said: {last_user[:200]}"
    return ChatResponse(trace_id=trace_id, session_id=body.session_id, answer=answer)


@router.post("/chat/stream")
async def chat_stream(req: Request, body: ChatRequest):
    trace_id = get_trace_id(req)

    async def gen():
        text = f"[mock-stream][trace={trace_id}] hello, this is a streaming response."
        for ch in text:
            yield ch
            await  asyncio.sleep(0.01)

    return StreamingResponse(gen(), media_type="text/plain")
