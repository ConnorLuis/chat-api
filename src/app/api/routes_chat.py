import time
from typing import Annotated
from fastapi import Body
from fastapi import APIRouter, Request, HTTPException

from src.app.core.errors import build_error
from src.app.core.logging import get_trace_id, logger  # 链路追踪ID
from src.app.core.prompt_registry import PromptRegistry, ensure_system_prompt
from src.app.core.run_logger import append_jsonl
from src.app.core.settings import settings
from src.app.llm.schemas import ChatRequest, ChatResponse, ErrorResponse # 请求/响应模型
from src.app.llm.engines import get_engine # 引擎工厂函数
from fastapi.responses import StreamingResponse # 流式响应
from src.app.core.sse import sse_event # SSE格式生成函数


# 创建一个路由实例，后续的接口都注册在这个实例上，方便模块化管理。
# APIRouter：FastAPI 的路由拆分工具，用于将接口按功能分组
router = APIRouter()
prompt_registry = PromptRegistry(settings.PROMPTS_DIR)

def engine_model(engine) -> str:
    return (getattr(engine, "model", None) or "unknown")

CHAT_OPENAPI_EXAMPLES = {
    "mock": {
        "summary": "mock example",
        "description": "Use mock provider for stable dev/testing.",
        "value": {
            "provider": "mock",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 64,
        },
    },
    "ollama": {
        "summary": "ollama example",
        "description": "Use ollama provider to call local LLM.",
        "value": {
            "provider": "ollama",
            "messages": [{"role": "user", "content": "一句话解释RAG"}],
            "max_tokens": 64,
        },
    },
}

# 普通的同步聊天接口
# 从请求的消息列表中提取用户最后一次发送的内容，拼接成模拟回复返回。
@router.post("/chat",
             response_model=ChatResponse,
             summary="Sync chat",
             description=(
                 "provider decides which backend engine to use (mock/ollama).\n\n"
                 "- Returns 200 with ChatResponse on success.\n"
                 "- Returns 502 with structured JSON `detail` when downstream model fails."
             ),
             responses={
                 502: {
                 "model": ErrorResponse,
                 "description": "Downstream model error (e.g. Ollama unreachable/timeout).",
                 }
             },
)
def chat(req: Request, body: Annotated[ChatRequest, Body(openapi_examples=CHAT_OPENAPI_EXAMPLES)]):
    # 从请求上下文获取trace ID（链路追踪）
    trace_id = get_trace_id(req)
    # 请求中的provider（mock/ollama）获取对应引擎实例
    engine = get_engine(body.provider)

    start = time.perf_counter()

    prompt_id = body.prompt_id
    prompt_version = body.prompt_version or "v1"
    prompt_vars = body.prompt_vars or {}

    messages = body.messages
    system_text = None
    if prompt_id:
        template = prompt_registry.get(prompt_id, prompt_version)
        system_text = prompt_registry.render(template, prompt_vars)
        messages = ensure_system_prompt(messages, system_text)
    try:
        # 调用引擎的非流式generate方法生成回复（Mock返回模拟内容，Ollama调用真实模型）
        answer = engine.generate(messages, body.temperature, body.top_p, body.max_tokens)
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        err = build_error(trace_id, engine.name, engine_model(engine), latency_ms, f"{engine.name} failed: {str(e)}")
        record = {
            "trace_id": trace_id,
            "mode": "chat",
            "provider": engine.name,
            "model": engine_model(engine),
            "prompt_id": prompt_id,
            "prompt_version": prompt_version if prompt_id else "none",
            "latency_ms": latency_ms,
            "prompt_chars": len(system_text) if system_text else 0,
            "output_chars": 0,
            "temperature": body.temperature,
            "top_p": body.top_p,
            "max_tokens": body.max_tokens,
            "error": str(e)
        }
        append_jsonl(settings.RUN_LOG_PATH, record)
        raise HTTPException(status_code=502, detail=err)

    latency_ms = int((time.perf_counter() - start) * 1000)
    metadata = {
        "provider": engine.name,
        "model": engine_model(engine),
        "latency_ms": latency_ms,
        "prompt_id": prompt_id or "none",
        "prompt_version": prompt_version if prompt_id else "none"
    }

    # 打印日志：便于后端监控
    record = {
        "trace_id": trace_id,
        "mode": "chat",
        "provider": engine.name,
        "model": engine_model(engine),
        "prompt_id": prompt_id,
        "prompt_version": prompt_version if prompt_id else "none",
        "latency_ms": latency_ms,
        "prompt_chars": len(system_text) if system_text else 0,
        "output_chars": len(answer),
        "temperature": body.temperature,
        "top_p": body.top_p,
        "max_tokens": body.max_tokens,
    }
    append_jsonl(settings.RUN_LOG_PATH, record)
    # 返回符合ChatResponse模型的响应
    return ChatResponse(trace_id=trace_id, session_id=body.session_id, answer=answer, metadata=metadata)

"""实现了标准化、可监控、可异常处理的 SSE 流式响应
    标准化的SSE响应：
        - 事件类型区分：meta初始化、token回复内容、usage统计、done结束、error异常。前端可按类型异常差异化处理
        - 数据格式统一：所有事件都通过sse_event生成，符合SSE标准，避免前端解析异常
    可监控：
        - 链路追踪：全流程携带 trace_id，日志 / 错误 / 统计都包含，便于定位问题；
        - 性能统计：记录耗时、token 数，可分析接口性能瓶颈；
        - 日志打印：后端输出关键指标，便于运维监控。
    兼容性与鲁棒性：
        - 引擎兼容：同时支持 Mock/Ollama 引擎，Mock 用于测试，Ollama 用于真实场景；
        - 异常兜底：所有异常都捕获并推送 error 事件，避免接口崩溃；
        - 边界处理：engine_model(engine) 兼容无 model 属性的引擎。
    前后端协同：
        - 前端可通过 meta 事件提前初始化；
        - token 事件实现打字机效果；
        - done 事件告知结束；
        - error 事件精准展示错误，提升用户体验。
"""
# 流式响应的异步聊天接口
@router.post(
            "/chat/stream",
            summary="Streaming chat (SSE)",
            description=(
                    "Server-Sent Events streaming endpoint.\n\n"
                    "Event types:\n"
                    "- meta: emitted first, includes trace_id/provider/model\n"
                    "- token: 0..N chunks\n"
                    "- usage: summary stats on success\n"
                    "- done: stream finished\n"
                    "- error: structured error JSON when downstream fails\n\n"
                    "When downstream fails, HTTP may still be 200 because the SSE channel is established; "
                    "the business error is delivered via `event: error`."
            ),
            responses={
                    200: {
                        "content": {
                            "text/event-stream": {
                                "example": (
                                    "event: meta\n"
                                    'data: {"trace_id":"...","provider":"ollama","model":"qwen2.5:7b"}\n\n'
                                    "event: token\n"
                                    "data: H\n\n"
                                    "event: token\n"
                                    "data: i\n\n"
                                    "event: usage\n"
                                    'data: {"trace_id":"...","provider":"ollama","model":"qwen2.5:7b","latency_ms":123,"token_events":3}\n\n'
                                    "event: done\n"
                                    "data: [DONE]\n\n"
                                )
                            }
                        }
                    }
            },
)
async def chat_stream(req: Request, body: Annotated[ChatRequest, Body(openapi_examples=CHAT_OPENAPI_EXAMPLES)]):
    # 从请求上下文获取trace ID（链路追踪）
    trace_id = get_trace_id(req)
    # 请求中的provider（mock/ollama）获取对应引擎实例
    engine = get_engine(body.provider)

    # 定义异步生成器函数（核心：逐段产生响应数据）
    async def gen():
        start = time.perf_counter() # 记录开始时间（统计耗时）

        messages = body.messages
        system_text = None

        prompt_id = body.prompt_id
        prompt_version = body.prompt_version or "v1"
        prompt_vars = body.prompt_vars or {}

        if prompt_id:
            template = prompt_registry.get(prompt_id, prompt_version)
            system_text = prompt_registry.render(template, prompt_vars)
            messages = ensure_system_prompt(messages, system_text)

        # 把 trace / provider 发出去，前端好做初始化
        yield sse_event("meta", {"trace_id": trace_id, "provider": engine.name, "model": engine_model(engine),"prompt_id": prompt_id or "none",
        "prompt_version": prompt_version if prompt_id else "none"})

        output_chars = 0
        token_events = 0

        try:
            # 调用引擎的stream方法（异步迭代器），逐token获取回复
            async for token in engine.stream(messages, body.temperature, body.top_p, body.max_tokens):
                token_events += 1
                output_chars += len(token)
                yield sse_event("token", token) # 推送token事件，逐段返回数据给前端

            # 计算耗时（毫秒）
            latency_ms = int((time.perf_counter() - start) * 1000)

            # 推送使用统计（usage事件）：包含性能、模型、token数等
            usage = {
                "trace_id": trace_id,
                "provider": engine.name,
                "model": engine_model(engine),
                "latency_ms": latency_ms,
                "token_events": token_events,
                "prompt_id": prompt_id or "none",
                "prompt_version": prompt_version if prompt_id else "none",
            }
            yield sse_event("usage", usage)
            yield sse_event("done", "[DONE]") # 推送结束事件，前端停止接收

            append_jsonl(settings.RUN_LOG_PATH, {
                "trace_id": trace_id,
                "mode": "stream",
                "provider": engine.name,
                "model": engine_model(engine),
                "prompt_id": prompt_id,
                "prompt_version": prompt_version if prompt_id else "none",
                "latency_ms": latency_ms,
                "token_events": token_events,
                "prompt_chars": len(system_text) if system_text else 0,
                "output_chars": output_chars,
            })

        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            err = build_error(trace_id, engine.name, engine_model(engine), latency_ms, f"{engine.name} failed: {str(e)}")
            err["prompt_id"] = prompt_id or "none"
            err["prompt_version"] = prompt_version if prompt_id else "none"
            # 异常时返回带trace_id的错误信息
            yield sse_event("error", err)
            # 流式异常也用 error 级别
            append_jsonl(settings.RUN_LOG_PATH, {
                "trace_id": trace_id,
                "mode": "stream",
                "provider": engine.name,
                "model": engine_model(engine),
                "prompt_id": prompt_id,
                "prompt_version": prompt_version if prompt_id else "none",
                "latency_ms": latency_ms,
                "token_events": token_events,
                "prompt_chars": len(system_text) if system_text else 0,
                "output_chars": 0,
                "temperature": body.temperature,
                "top_p": body.top_p,
                "max_tokens": body.max_tokens,
                "error": str(e)
            })


    # 返回流式响应，指定媒体类型为纯文本
    return StreamingResponse(gen(), media_type="text/event-stream")
