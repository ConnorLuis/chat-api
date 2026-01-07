import asyncio
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from src.app.core.logging import get_trace_id
from src.app.llm.schemas import ChatRequest, ChatResponse
from src.app.llm.engines import get_engine

# 创建一个路由实例，后续的接口都注册在这个实例上，方便模块化管理。
# APIRouter：FastAPI 的路由拆分工具，用于将接口按功能分组
router = APIRouter()


# 普通的同步聊天接口
# 从请求的消息列表中提取用户最后一次发送的内容，拼接成模拟回复返回。
@router.post("/chat", response_model=ChatResponse)
def chat(req: Request, body: ChatRequest):
    # 从请求上下文获取trace ID（链路追踪）
    trace_id = get_trace_id(req)
    # 请求中的provider（mock/ollama）获取对应引擎实例
    engine = get_engine(body.provider)

    try:
        # 调用引擎的generate方法生成回复（Mock返回模拟内容，Ollama调用真实模型）
        answer = engine.generate(body.messages, body.temperature, body.top_p, body.max_tokens)
    except Exception as e:
        # 捕获异常，返回502错误（网关错误），携带trace_id方便排查
        raise HTTPException(status_code=502, detail={"trace_id": trace_id, "error": f"{engine.name} failed: {str(e)}"})

    # 返回符合ChatResponse模型的响应
    return ChatResponse(trace_id=trace_id, session_id=body.session_id, answer=answer)


# 流式响应的异步聊天接口
@router.post("/chat/stream")
async def chat_stream(req: Request, body: ChatRequest):
    # 从请求上下文获取trace ID（链路追踪）
    trace_id = get_trace_id(req)
    # 请求中的provider（mock/ollama）获取对应引擎实例
    engine = get_engine(body.provider)

    # 定义异步生成器函数（核心：逐段产生响应数据）
    async def gen():
        try:
            # 调用引擎的stream方法（异步迭代器），逐token获取回复
            async for token in engine.stream(body.messages, body.temperature, body.top_p, body.max_tokens):
                yield token # 逐段返回数据给前端
        except Exception as e:
            # 异常时返回带trace_id的错误信息
            yield f"\n[error trace={trace_id}] {engine.name} failed: {str(e)}\n"

    # 返回流式响应，指定媒体类型为纯文本
    return StreamingResponse(gen(), media_type="text/plain")
