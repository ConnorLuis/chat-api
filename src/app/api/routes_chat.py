import time
from typing import Annotated
from fastapi import Body
from fastapi import APIRouter, Request, HTTPException

from src.app.core.errors import build_error
from src.app.core.logging import get_trace_id  # 链路追踪ID
from src.app.llm.prompt_registry import PromptRegistry, ensure_system_prompt
from src.app.llm.run_logger import append_jsonl
from src.app.core.settings import settings
from src.app.llm.schemas import ChatRequest, ChatResponse, ErrorResponse, RagMetadata, Citation  # 请求/响应模型
from src.app.llm.engines import get_engine # 引擎工厂函数
from fastapi.responses import StreamingResponse # 流式响应
from src.app.core.sse import sse_event # SSE格式生成函数
from src.app.rag.factory import get_rag_backend


# 创建一个路由实例，后续的接口都注册在这个实例上，方便模块化管理。
# APIRouter：FastAPI 的路由拆分工具，用于将接口按功能分组
router = APIRouter()
prompt_registry = PromptRegistry(settings.PROMPTS_DIR)

def engine_model(engine) -> str:
    return (getattr(engine, "model", None) or "unknown")

def build_rag_prompt_context(context_text: str) -> str:
    return f"你是一个严谨助手 仅基于以下资料回答，并在回答末尾列出引用编号 \n\n<CONTEXT>\n{context_text}"


def to_llm_citations(citations) -> list[Citation]:
    return [
        Citation(
            doc_id=c.doc_id,
            chunk_id=c.chunk_id,
            source=c.source,
            title=c.title,
        )
        for c in citations
    ]

RAG_TIMING_KEYS = [
    "embedding_ms",
    "retrieval_ms",
    "rerank_ms",
    "context_build_ms",
    "total_ms",
]

def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def apply_rag_extra_to_meta(rag_meta: RagMetadata, extra: dict | None) -> None:
    extra = extra or {}

    rag_meta.backend = extra.get("backend")
    rag_meta.vectorstore = extra.get("vectorstore")

    for key in RAG_TIMING_KEYS:
        setattr(rag_meta, key, _safe_int(extra.get(key), 0))


def rag_extra_for_stream(extra: dict | None) -> dict:
    extra = extra or {}

    data = {
        "backend": extra.get("backend"),
        "vectorstore": extra.get("vectorstore"),
    }

    for key in RAG_TIMING_KEYS:
        data[key] = _safe_int(extra.get(key), 0)

    return data

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

def _last_user_text(messages) -> str | None:
    for m in reversed(messages or []):
        if getattr(m, "role", None) == "user":
            c = (getattr(m, "content", None) or "").strip()
            if c:
                return c
    return None

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
    context = None
    hits = []
    top_k = int(body.kb_top_k or settings.KB_TOP_K)
    rag_error = None
    candidate_k=0
    rag_meta = RagMetadata(
        enabled=bool(body.use_kb),
        top_k=top_k if body.use_kb else 0,
        citations=[],
        hits=0,
        candidate_k=0,
        error=None,
    )
    try:
        if body.use_kb:
            query = _last_user_text(messages)
            if not query:
                # KB 开启但没有可用 query：当作无命中（但 rag 仍然是 enabled=true）
                rag_meta.enabled = True
                rag_meta.top_k = top_k
                rag_meta.candidate_k = 0
                rag_meta.hits = 0
                rag_meta.citations = []
                rag_meta.error = None
                context = None
            else:
                rag_backend = get_rag_backend()
                rag_result = rag_backend.build_context(query=query, top_k=top_k)

                llm_citations = to_llm_citations(rag_result.citations)

                if not rag_result.hits:
                    context = None
                else:
                    context = build_rag_prompt_context(rag_result.context)

                rag_meta.enabled = True
                rag_meta.top_k = rag_result.top_k
                rag_meta.candidate_k = rag_result.candidate_k
                rag_meta.hits = rag_result.hits
                rag_meta.citations = llm_citations
                rag_meta.error = rag_result.error
                apply_rag_extra_to_meta(rag_meta, rag_result.extra)

    except Exception as e:
        rag_error = str(e)
        hits = []
        context = None

        rag_meta.enabled = True
        rag_meta.top_k = top_k
        rag_meta.candidate_k = candidate_k  # 如果早期异常这里可能还是 0，没关系
        rag_meta.hits = 0
        rag_meta.citations = []
        rag_meta.error = rag_error
        rag_meta.backend = settings.RAG_BACKEND
    context_chars = len(context) if context else 0
    parts = []
    if system_text:
        parts.append(system_text)
    if context:
        parts.append(context)
    final_system_text = "\n\n".join(parts) if parts else None
    if final_system_text:
        messages = ensure_system_prompt(messages, final_system_text)
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
            "rag_enabled": body.use_kb,
            "rag_hits": rag_meta.hits if rag_meta else 0,
            "rag_error": rag_error,
            "context_chars": context_chars,
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
        "prompt_version": prompt_version if prompt_id else "none",
        "rag": rag_meta,
        "context_chars": context_chars,
        "rag_error": rag_error,
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
        "rag_enabled": body.use_kb,
        "rag_hits": rag_meta.hits if rag_meta else 0,
        "rag_error": rag_error,
        "context_chars": context_chars,
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

        rag_enabled = bool(body.use_kb)
        top_k = int(body.kb_top_k or settings.KB_TOP_K)

        hits_list = []
        hits = 0
        citations = []
        context = None
        context_chars = 0
        rag_error = None
        candidate_k = 0

        # 统一形状：永远有 rag（use_kb=false 时 enabled=false + top_k=0）
        rag_dict = {
            "enabled": rag_enabled,
            "top_k": top_k if rag_enabled else 0,
            "hits": 0,
            "context_chars": 0,
            "candidate_k": 0,
            "error": None,
            **rag_extra_for_stream({
                "backend": settings.RAG_BACKEND if rag_enabled else None,
            }),
        }
        try:
            if rag_enabled:
                query = _last_user_text(messages)

                if not query:
                    context = None
                    hits = 0
                    citations = []
                    rag_dict.update({
                        "enabled": True,
                        "top_k": top_k,
                        "hits": 0,
                        "candidate_k": 0,
                        "error": None,
                        **rag_extra_for_stream({
                            "backend": settings.RAG_BACKEND,
                        }),
                    })
                else:
                    rag_backend = get_rag_backend()
                    rag_result = rag_backend.build_context(query=query, top_k=top_k)

                    citations = to_llm_citations(rag_result.citations)
                    hits = rag_result.hits
                    candidate_k = rag_result.candidate_k

                    if not rag_result.hits:
                        context = None
                    else:
                        context = build_rag_prompt_context(rag_result.context)

                    rag_dict.update({
                        "enabled": True,
                        "top_k": rag_result.top_k,
                        "hits": rag_result.hits,
                        "candidate_k": rag_result.candidate_k,
                        "error": rag_result.error,
                        **rag_extra_for_stream(rag_result.extra),
                    })
        except Exception as e:
            rag_error = str(e)
            citations = []
            hits = 0
            context = None

            rag_dict.update({
                "enabled": True,
                "top_k": top_k,
                "candidate_k": candidate_k,
                "hits": 0,
                "error": rag_error,
                **rag_extra_for_stream({
                    "backend": settings.RAG_BACKEND,
                }),
            })

        context_chars = len(context) if context else 0
        rag_dict["context_chars"] = context_chars
        parts = []
        if system_text:
            parts.append(system_text)
        if context:
            parts.append(context)
        final_system_text = "\n\n".join(parts) if parts else None
        if final_system_text:
            messages = ensure_system_prompt(messages, final_system_text)

        # 把 trace / provider 发出去，前端好做初始化
        meta = {
            "trace_id": trace_id,
            "provider": engine.name,
            "model": engine_model(engine),
            "prompt_id": prompt_id or "none",
            "prompt_version": prompt_version if prompt_id else "none",
            "rag": rag_dict,
        }
        yield sse_event("meta", meta)

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

            citations_payload = [c.model_dump() if hasattr(c, "model_dump") else c for c in citations]

            # 推送使用统计（usage事件）：包含性能、模型、token数等
            usage = {
                "trace_id": trace_id,
                "provider": engine.name,
                "model": engine_model(engine),
                "latency_ms": latency_ms,
                "token_events": token_events,
                "prompt_id": prompt_id or "none",
                "prompt_version": prompt_version if prompt_id else "none",
                "rag": {
                    **rag_dict,
                    "citations": citations_payload,
                    "error": rag_error or rag_dict.get("error"),
                },
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
                "rag_enabled": rag_enabled,
                "kb_top_k":top_k,
                "rag_hits": hits,
                "context_chars": context_chars,
                "rag_error": rag_error,
                "citations_count": len(citations)
            })

        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            err = build_error(trace_id, engine.name, engine_model(engine), latency_ms, f"{engine.name} failed: {str(e)}")
            err["prompt_id"] = prompt_id or "none"
            err["prompt_version"] = prompt_version if prompt_id else "none"
            err["rag"] = {
                **rag_dict,
                "citations": citations_payload if "citations_payload" in locals() else [],
                "error": str(e),
            }
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
                "rag_enabled": rag_enabled,
                "kb_top_k": top_k,
                "rag_hits": hits,
                "context_chars": context_chars,
                "rag_error": rag_error,
                "error": str(e)
            })


    # 返回流式响应，指定媒体类型为纯文本
    return StreamingResponse(gen(), media_type="text/event-stream")
