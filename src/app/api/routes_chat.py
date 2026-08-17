import asyncio
import time
from typing import Annotated
from fastapi import Body
from fastapi import APIRouter, Request, HTTPException

from src.app.core.errors import build_error
from src.app.core.logging import get_trace_id  # 链路追踪ID
from src.app.llm.prompt_registry import PromptRegistry, ensure_system_prompt
from src.app.llm.run_logger import append_jsonl
from src.app.core.settings import settings
from src.app.db.session import (
    get_session_factory,
)
from src.app.conversations import (
    ContextMessage,
    build_context_window,
    load_conversation_history,
)
from src.app.services import (
    ConversationNotFoundError,
    NewUsageRecord,
    USAGE_STATUS_CLIENT_DISCONNECTED,
    USAGE_STATUS_PERSISTENCE_FAILED,
    USAGE_STATUS_PROVIDER_FAILED,
    USAGE_STATUS_SUCCEEDED,
)
from src.app.llm.schemas import ChatRequest, ChatResponse, ErrorResponse, RagMetadata, Citation  # 请求/响应模型
from src.app.llm.providers import (
    build_provider_request,
    get_chat_provider,
    provider_execution_payload,
    provider_execution_target,
)
from src.app.usage import (
    USAGE_SOURCE_PROVIDER_NATIVE,
    resolve_terminal_usage_snapshot,
    resolve_usage_snapshot,
    unavailable_usage_snapshot,
)
from src.app.usage.persistence import (
    persist_sync_exchange_and_usage,
    persist_usage_only,
)
from fastapi.responses import StreamingResponse # 流式响应
from starlette.concurrency import run_in_threadpool
from src.app.core.sse import sse_event # SSE格式生成函数
from src.app.rag.factory import get_rag_backend


# 创建一个路由实例，后续的接口都注册在这个实例上，方便模块化管理。
# APIRouter：FastAPI 的路由拆分工具，用于将接口按功能分组
router = APIRouter()
prompt_registry = PromptRegistry(settings.PROMPTS_DIR)

def provider_model(
    provider,
    requested_model: str | None = None,
) -> str:
    """解析当前请求实际使用的模型名，并保证永远返回字符串。"""

    try:
        model = provider.resolve_model(requested_model)
    except Exception:
        model = (
            requested_model
            or getattr(provider, "default_model", None)
            or getattr(provider, "model", None)
        )

    return model or "unknown"


# 暂时保留旧名称，避免其他模块或历史代码直接导入时失效。
engine_model = provider_model


def request_caller_key_id(
    request: Request,
) -> str | None:
    caller = getattr(
        request.state,
        "caller",
        None,
    )

    if caller is None:
        return None

    return caller.key_id


def decimal_to_json(
    value,
) -> str | None:
    if value is None:
        return None

    return format(value, "f")


def build_cost_payload(
    cost_record,
) -> dict | None:
    if cost_record is None:
        return None

    return {
        "pricing_key": (
            cost_record.pricing_key
        ),
        "matched_pricing_key": (
            cost_record.matched_pricing_key
        ),
        "pricing_version": (
            cost_record.pricing_version
        ),
        "currency": cost_record.currency,
        "unit_tokens": (
            cost_record.unit_tokens
        ),
        "cost_status": (
            cost_record.cost_status
        ),
        "prompt_price_per_unit": (
            decimal_to_json(
                cost_record
                .prompt_price_per_unit
            )
        ),
        "completion_price_per_unit": (
            decimal_to_json(
                cost_record
                .completion_price_per_unit
            )
        ),
        "prompt_cost": (
            decimal_to_json(
                cost_record.prompt_cost
            )
        ),
        "completion_cost": (
            decimal_to_json(
                cost_record.completion_cost
            )
        ),
        "estimated_cost": (
            decimal_to_json(
                cost_record.estimated_cost
            )
        ),
    }


def build_usage_payload(
    *,
    request_id: str | None,
    status: str,
    snapshot,
    cost_record=None,
) -> dict:
    """构造同步/流式共享的 usage/cost payload."""

    return {
        "request_id": request_id,
        "status": status,
        "usage_source": (
            snapshot.usage_source
        ),
        "prompt_tokens": (
            snapshot.prompt_tokens
        ),
        "completion_tokens": (
            snapshot.completion_tokens
        ),
        "total_tokens": (
            snapshot.total_tokens
        ),
        "cost": build_cost_payload(
            cost_record
        ),
    }

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

RAG_FUSION_KEYS = [
    "retrieval_mode",
    "fusion",
]

RAG_WEIGHT_KEYS = [
    "vector_weight",
    "lexical_weight",
]

def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def apply_rag_extra_to_meta(rag_meta: RagMetadata, extra: dict | None) -> None:
    extra = extra or {}

    rag_meta.backend = extra.get("backend")
    rag_meta.vectorstore = extra.get("vectorstore")

    for key in RAG_TIMING_KEYS:
        setattr(rag_meta, key, _safe_int(extra.get(key), 0))

    for key in RAG_FUSION_KEYS:
        setattr(rag_meta, key, extra.get(key))

    for key in RAG_WEIGHT_KEYS:
        setattr(rag_meta, key, _safe_float(extra.get(key), 0.0))


def rag_extra_for_stream(extra: dict | None) -> dict:
    extra = extra or {}

    data = {
        "backend": extra.get("backend"),
        "vectorstore": extra.get("vectorstore"),
    }

    for key in RAG_TIMING_KEYS:
        data[key] = _safe_int(extra.get(key), 0)

    for key in RAG_FUSION_KEYS:
        data[key] = extra.get(key)

    for key in RAG_WEIGHT_KEYS:
        data[key] = _safe_float(extra.get(key), 0.0)

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
            "model": "qwen2.5:7b",
            "messages": [{"role": "user", "content": "一句话解释RAG"}],
            "max_tokens": 64,
        },
    },
    "openai": {
        "summary": "OpenAI-compatible example",
        "description": (
            "Use the OpenAI provider or an OpenAI-compatible endpoint. "
            "Requires OPENAI_API_KEY and a request/default model."
        ),
        "value": {
            "provider": "openai",
            "model": "your-model-name",
            "messages": [{"role": "user", "content": "Hello"}],
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
    # 从请求上下文获取 trace ID。
    trace_id = get_trace_id(req)
    caller_key_id = (
        request_caller_key_id(req)
    )

    conversation_id = body.conversation_id
    history_messages: tuple[ContextMessage, ...] = ()

    # 仅显式传入 conversation_id 时启用持久化会话。
    # 使用短 Session 读取，Provider 调用期间不持有数据库连接。
    if conversation_id is not None:
        try:
            snapshot = load_conversation_history(
                session_factory=get_session_factory(),
                conversation_id=conversation_id,
                limit=(
                    settings
                    .CONVERSATION_HISTORY_FETCH_LIMIT
                ),
            )
            history_messages = snapshot.messages

        except ConversationNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            ) from exc

    # 通过统一 ProviderFactory 获取本次请求的模型 Provider。
    provider = get_chat_provider(body.provider)
    active_provider = provider.name
    active_model = provider_model(provider, body.model)

    start = time.perf_counter()

    prompt_id = body.prompt_id
    prompt_version = body.prompt_version or "v1"
    prompt_vars = body.prompt_vars or {}

    # body.messages 永远表示本次新增的显式消息，
    # 持久化历史由服务端读取。
    current_messages = list(body.messages)
    messages = current_messages
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
    context_window = None

    if conversation_id is not None:
        context_window = build_context_window(
            history=history_messages,
            current=current_messages,
            system_text=final_system_text,
            max_turns=(
                settings
                .CONVERSATION_HISTORY_MAX_TURNS
            ),
            token_budget=(
                settings
                .CONVERSATION_CONTEXT_TOKEN_BUDGET
            ),
        )

        messages = list(
            context_window.messages
        )
    else:
        messages = current_messages

    # PromptHub / RAG 自动 system prompt 只参与当前 Provider
    # 请求，不写入 Conversation Message 表。
    if final_system_text:
        messages = ensure_system_prompt(
            messages,
            final_system_text,
        )

    provider_request = build_provider_request(
        messages,
        model=body.model,
        temperature=body.temperature,
        top_p=body.top_p,
        max_tokens=body.max_tokens,
    )
    execution_payload = None

    try:
        provider_response = provider.chat(
            provider_request
        )

    except Exception as e:
        execution = getattr(
            e,
            "execution",
            None,
        )
        active_provider, active_model = (
            provider_execution_target(
                execution,
                provider=active_provider,
                model=active_model,
            )
        )
        execution_payload = (
            provider_execution_payload(
                execution
            )
        )
        latency_ms = int(
            (
                time.perf_counter()
                - start
            )
            * 1000
        )

        unavailable = (
            unavailable_usage_snapshot()
        )
        usage_record_error = None

        try:
            persist_usage_only(
                session_factory=(
                    get_session_factory()
                ),
                usage=NewUsageRecord(
                    caller_key_id=caller_key_id,
                    trace_id=trace_id,
                    conversation_id=(
                        conversation_id
                    ),
                    request_kind="chat_sync",
                    provider=active_provider,
                    model=active_model,
                    status=(
                        USAGE_STATUS_PROVIDER_FAILED
                    ),
                    usage_source=(
                        unavailable.usage_source
                    ),
                    prompt_tokens=None,
                    completion_tokens=None,
                    total_tokens=None,
                    latency_ms=latency_ms,
                    error_type=(
                        type(e).__name__
                    ),
                ),
            )

        except Exception as usage_exc:
            # Accounting 失败不能覆盖原始 Provider 502。
            usage_record_error = str(
                usage_exc
            )

        err = build_error(
            trace_id,
            active_provider,
            active_model,
            latency_ms,
            (
                f"{active_provider} failed: "
                f"{str(e)}"
            ),
            provider_execution=(
                execution_payload
            ),
        )

        record = {
            "trace_id": trace_id,
            "mode": "chat",
            "provider": active_provider,
            "model": active_model,
            "prompt_id": prompt_id,
            "prompt_version": (
                prompt_version
                if prompt_id
                else "none"
            ),
            "latency_ms": latency_ms,
            "prompt_chars": (
                len(system_text)
                if system_text
                else 0
            ),
            "output_chars": 0,
            "temperature": body.temperature,
            "top_p": body.top_p,
            "max_tokens": body.max_tokens,
            "rag_enabled": body.use_kb,
            "rag_hits": (
                rag_meta.hits
                if rag_meta
                else 0
            ),
            "rag_error": rag_error,
            "context_chars": context_chars,
            "error": str(e),
            "provider_execution": (
                execution_payload
            ),
        }

        if usage_record_error is not None:
            record["usage_record_error"] = (
                usage_record_error
            )

        append_jsonl(
            settings.RUN_LOG_PATH,
            record,
        )

        raise HTTPException(
            status_code=502,
            detail=err,
        )

    answer = provider_response.content

    active_provider = (
        provider_response.provider
        or active_provider
    )
    active_model = (
        provider_response.model
        or active_model
    )
    execution_payload = (
        provider_execution_payload(
            provider_response.execution
        )
    )

    latency_ms = int(
        (
            time.perf_counter()
            - start
        )
        * 1000
    )

    usage_snapshot = resolve_usage_snapshot(
        provider_usage=(
            provider_response.usage
        ),
        messages=provider_request.messages,
        completion_text=answer,
    )

    success_usage = NewUsageRecord(
        caller_key_id=caller_key_id,
        trace_id=trace_id,
        conversation_id=conversation_id,
        request_kind="chat_sync",
        provider=active_provider,
        model=active_model,
        status=USAGE_STATUS_SUCCEEDED,
        usage_source=(
            usage_snapshot.usage_source
        ),
        prompt_tokens=(
            usage_snapshot.prompt_tokens
        ),
        completion_tokens=(
            usage_snapshot.completion_tokens
        ),
        total_tokens=(
            usage_snapshot.total_tokens
        ),
        latency_ms=latency_ms,
    )

    # Message.token_count 只保存 Provider 原生且完整的
    # assistant completion token 数；本地估算的请求级
    # usage 仅进入 UsageRecord。
    assistant_token_count = (
        usage_snapshot.completion_tokens
        if (
            usage_snapshot.usage_source
            == USAGE_SOURCE_PROVIDER_NATIVE
        )
        else None
    )

    try:
        usage_result = (
            persist_sync_exchange_and_usage(
                session_factory=(
                    get_session_factory()
                ),
                conversation_id=(
                    conversation_id
                ),
                request_messages=[
                    ContextMessage(
                        role=message.role,
                        content=message.content,
                    )
                    for message
                    in current_messages
                ],
                assistant_content=answer,
                provider=active_provider,
                model=active_model,
                assistant_token_count=(
                    assistant_token_count
                ),
                usage=success_usage,
            )
        )

    except ConversationNotFoundError as exc:
        # Provider 已完成调用但会话被并发删除：
        # 消息事务已回滚，另行保留 consumed usage。
        try:
            persist_usage_only(
                session_factory=(
                    get_session_factory()
                ),
                usage=NewUsageRecord(
                    caller_key_id=caller_key_id,
                    trace_id=trace_id,
                    conversation_id=(
                        conversation_id
                    ),
                    request_kind="chat_sync",
                    provider=active_provider,
                    model=active_model,
                    status=(
                        USAGE_STATUS_PERSISTENCE_FAILED
                    ),
                    usage_source=(
                        usage_snapshot
                        .usage_source
                    ),
                    prompt_tokens=(
                        usage_snapshot
                        .prompt_tokens
                    ),
                    completion_tokens=(
                        usage_snapshot
                        .completion_tokens
                    ),
                    total_tokens=(
                        usage_snapshot
                        .total_tokens
                    ),
                    latency_ms=latency_ms,
                    error_type=(
                        "conversation_not_found"
                    ),
                ),
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        ) from exc

    except Exception as exc:
        usage_record_error = None

        try:
            persist_usage_only(
                session_factory=(
                    get_session_factory()
                ),
                usage=NewUsageRecord(
                    caller_key_id=caller_key_id,
                    trace_id=trace_id,
                    conversation_id=(
                        conversation_id
                    ),
                    request_kind="chat_sync",
                    provider=active_provider,
                    model=active_model,
                    status=(
                        USAGE_STATUS_PERSISTENCE_FAILED
                    ),
                    usage_source=(
                        usage_snapshot
                        .usage_source
                    ),
                    prompt_tokens=(
                        usage_snapshot
                        .prompt_tokens
                    ),
                    completion_tokens=(
                        usage_snapshot
                        .completion_tokens
                    ),
                    total_tokens=(
                        usage_snapshot
                        .total_tokens
                    ),
                    latency_ms=latency_ms,
                    error_type=(
                        type(exc).__name__
                    ),
                ),
            )

        except Exception as usage_exc:
            usage_record_error = str(
                usage_exc
            )

        error_message = (
            "conversation or usage persistence "
            f"failed: {exc}"
        )

        if usage_record_error is not None:
            error_message += (
                "; failure accounting also "
                f"failed: {usage_record_error}"
            )

        err = build_error(
            trace_id,
            active_provider,
            active_model,
            latency_ms,
            error_message,
        )

        raise HTTPException(
            status_code=500,
            detail=err,
        ) from exc

    metadata = {
        "provider": active_provider,
        "model": active_model,
        "latency_ms": latency_ms,
        "prompt_id": prompt_id or "none",
        "prompt_version": prompt_version if prompt_id else "none",
        "rag": rag_meta,
        "context_chars": context_chars,
        "rag_error": rag_error,
        "usage": build_usage_payload(
            request_id=(
                usage_result.request_id
            ),
            status=(
                USAGE_STATUS_SUCCEEDED
            ),
            snapshot=usage_snapshot,
            cost_record=(
                usage_result.usage_cost
            ),
        ),
        "provider_execution": execution_payload,
    }

    # 打印日志：便于后端监控
    record = {
        "trace_id": trace_id,
        "mode": "chat",
        "provider": active_provider,
        "model": active_model,
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
        "provider_execution": execution_payload,
    }
    append_jsonl(settings.RUN_LOG_PATH, record)
    # 返回符合ChatResponse模型的响应
    return ChatResponse(
        trace_id=trace_id,
        session_id=body.session_id,
        conversation_id=conversation_id,
        answer=answer,
        metadata=metadata,
    )

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
        - 边界处理：active_model 兼容无 model 属性的引擎。
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
async def chat_stream(
    req: Request,
    body: Annotated[
        ChatRequest,
        Body(
            openapi_examples=(
                CHAT_OPENAPI_EXAMPLES
            )
        ),
    ],
):
    trace_id = get_trace_id(req)
    caller_key_id = (
        request_caller_key_id(req)
    )

    conversation_id = body.conversation_id
    history_messages: tuple[
        ContextMessage,
        ...,
    ] = ()

    # 在 SSE 响应建立前校验 Conversation，
    # 不存在时可以正常返回 HTTP 404。
    if conversation_id is not None:
        try:
            snapshot = await run_in_threadpool(
                load_conversation_history,
                session_factory=(
                    get_session_factory()
                ),
                conversation_id=conversation_id,
                limit=(
                    settings
                    .CONVERSATION_HISTORY_FETCH_LIMIT
                ),
            )

            history_messages = (
                snapshot.messages
            )

        except ConversationNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            ) from exc

    provider = get_chat_provider(
        body.provider
    )

    async def gen():
        start = time.perf_counter()

        active_provider = provider.name
        active_model = provider_model(
            provider,
            body.model,
        )

        # body.messages 只表示本次显式提交的消息。
        current_messages = list(
            body.messages
        )
        messages = current_messages

        prompt_id = body.prompt_id
        prompt_version = (
            body.prompt_version
            or "v1"
        )
        prompt_vars = (
            body.prompt_vars
            or {}
        )

        system_text = None

        if prompt_id:
            template = prompt_registry.get(
                prompt_id,
                prompt_version,
            )

            system_text = (
                prompt_registry.render(
                    template,
                    prompt_vars,
                )
            )

        rag_enabled = bool(
            body.use_kb
        )
        top_k = int(
            body.kb_top_k
            or settings.KB_TOP_K
        )

        hits = 0
        citations = []
        context = None
        context_chars = 0
        rag_error = None
        candidate_k = 0

        rag_dict = {
            "enabled": rag_enabled,
            "top_k": (
                top_k
                if rag_enabled
                else 0
            ),
            "hits": 0,
            "context_chars": 0,
            "candidate_k": 0,
            "error": None,
            **rag_extra_for_stream({
                "backend": (
                    settings.RAG_BACKEND
                    if rag_enabled
                    else None
                ),
            }),
        }

        try:
            if rag_enabled:
                query = _last_user_text(
                    current_messages
                )

                if not query:
                    rag_dict.update({
                        "enabled": True,
                        "top_k": top_k,
                        "hits": 0,
                        "candidate_k": 0,
                        "error": None,
                        **rag_extra_for_stream({
                            "backend": (
                                settings.RAG_BACKEND
                            ),
                        }),
                    })

                else:
                    rag_backend = (
                        get_rag_backend()
                    )

                    rag_result = (
                        rag_backend
                        .build_context(
                            query=query,
                            top_k=top_k,
                        )
                    )

                    citations = (
                        to_llm_citations(
                            rag_result.citations
                        )
                    )
                    hits = rag_result.hits
                    candidate_k = (
                        rag_result.candidate_k
                    )

                    if rag_result.hits:
                        context = (
                            build_rag_prompt_context(
                                rag_result.context
                            )
                        )

                    rag_dict.update({
                        "enabled": True,
                        "top_k": (
                            rag_result.top_k
                        ),
                        "hits": (
                            rag_result.hits
                        ),
                        "candidate_k": (
                            rag_result
                            .candidate_k
                        ),
                        "error": (
                            rag_result.error
                        ),
                        **rag_extra_for_stream(
                            rag_result.extra
                        ),
                    })

        except Exception as exc:
            rag_error = str(exc)
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
                    "backend": (
                        settings.RAG_BACKEND
                    ),
                }),
            })

        context_chars = (
            len(context)
            if context
            else 0
        )

        rag_dict[
            "context_chars"
        ] = context_chars

        parts: list[str] = []

        if system_text:
            parts.append(system_text)

        if context:
            parts.append(context)

        final_system_text = (
            "\n\n".join(parts)
            if parts
            else None
        )

        context_window = None

        if conversation_id is not None:
            context_window = (
                build_context_window(
                    history=history_messages,
                    current=current_messages,
                    system_text=(
                        final_system_text
                    ),
                    max_turns=(
                        settings
                        .CONVERSATION_HISTORY_MAX_TURNS
                    ),
                    token_budget=(
                        settings
                        .CONVERSATION_CONTEXT_TOKEN_BUDGET
                    ),
                )
            )

            messages = list(
                context_window.messages
            )

        if final_system_text:
            messages = ensure_system_prompt(
                messages,
                final_system_text,
            )

        provider_request = (
            build_provider_request(
                messages,
                model=body.model,
                temperature=(
                    body.temperature
                ),
                top_p=body.top_p,
                max_tokens=(
                    body.max_tokens
                ),
            )
        )

        context_window_payload = (
            {
                "history_messages": (
                    context_window
                    .history_messages
                ),
                "current_messages": (
                    context_window
                    .current_messages
                ),
                "truncated": (
                    context_window
                    .truncated
                ),
                "estimated_tokens": (
                    context_window
                    .estimated_tokens
                ),
            }
            if context_window is not None
            else None
        )

        meta = {
            "trace_id": trace_id,
            "conversation_id": (
                conversation_id
            ),
            "provider": active_provider,
            "model": active_model,
            "prompt_id": (
                prompt_id
                or "none"
            ),
            "prompt_version": (
                prompt_version
                if prompt_id
                else "none"
            ),
            "context_window": (
                context_window_payload
            ),
            "rag": rag_dict,
        }

        yield sse_event(
            "meta",
            meta,
        )

        output_parts: list[str] = []
        output_chars = 0
        token_events = 0
        provider_usage = None
        execution_payload = None

        stream_iterator = (
            provider
            .stream(provider_request)
            .__aiter__()
        )

        try:
            try:
                async for chunk in stream_iterator:
                    if chunk.provider:
                        active_provider = (
                            chunk.provider
                        )

                    if chunk.model:
                        active_model = (
                            chunk.model
                        )

                    if chunk.execution is not None:
                        execution_payload = (
                            provider_execution_payload(
                                chunk.execution
                            )
                        )
                        active_provider, active_model = (
                            provider_execution_target(
                                chunk.execution,
                                provider=active_provider,
                                model=active_model,
                            )
                        )

                    if chunk.usage is not None:
                        provider_usage = (
                            chunk.usage
                        )

                    token = chunk.delta

                    # 空字符串可能只是 terminal /
                    # usage chunk；单空格必须保留。
                    if token == "":
                        continue

                    token_events += 1
                    output_chars += len(token)
                    output_parts.append(token)

                    yield sse_event(
                        "token",
                        token,
                    )

            except (
                asyncio.CancelledError,
                GeneratorExit,
            ):
                # Provider 未完整结束前客户端断开：
                # 不保存 Message，只记录本次请求级 accounting。
                latency_ms = int(
                    (
                        time.perf_counter()
                        - start
                    )
                    * 1000
                )

                partial_content = "".join(
                    output_parts
                )

                disconnect_snapshot = (
                    resolve_terminal_usage_snapshot(
                        provider_usage=(
                            provider_usage
                        ),
                        messages=(
                            provider_request.messages
                        ),
                        completion_text=(
                            partial_content
                        ),
                    )
                )

                try:
                    await asyncio.shield(
                        run_in_threadpool(
                            persist_usage_only,
                            session_factory=(
                                get_session_factory()
                            ),
                            usage=NewUsageRecord(
                                caller_key_id=caller_key_id,
                                trace_id=trace_id,
                                conversation_id=(
                                    conversation_id
                                ),
                                request_kind=(
                                    "chat_stream"
                                ),
                                provider=(
                                    active_provider
                                ),
                                model=active_model,
                                status=(
                                    USAGE_STATUS_CLIENT_DISCONNECTED
                                ),
                                usage_source=(
                                    disconnect_snapshot
                                    .usage_source
                                ),
                                prompt_tokens=(
                                    disconnect_snapshot
                                    .prompt_tokens
                                ),
                                completion_tokens=(
                                    disconnect_snapshot
                                    .completion_tokens
                                ),
                                total_tokens=(
                                    disconnect_snapshot
                                    .total_tokens
                                ),
                                latency_ms=(
                                    latency_ms
                                ),
                                error_type=(
                                    "client_disconnect"
                                ),
                            ),
                        )
                    )

                except BaseException:
                    # 不能让 accounting 清理错误覆盖取消语义。
                    pass

                raise

            except Exception as exc:
                execution = getattr(
                    exc,
                    "execution",
                    None,
                )

                if execution is not None:
                    active_provider, active_model = (
                        provider_execution_target(
                            execution,
                            provider=active_provider,
                            model=active_model,
                        )
                    )
                    execution_payload = (
                        provider_execution_payload(
                            execution
                        )
                    )

                latency_ms = int(
                    (
                        time.perf_counter()
                        - start
                    )
                    * 1000
                )

                partial_content = "".join(
                    output_parts
                )

                failure_snapshot = (
                    resolve_terminal_usage_snapshot(
                        provider_usage=(
                            provider_usage
                        ),
                        messages=(
                            provider_request.messages
                        ),
                        completion_text=(
                            partial_content
                        ),
                    )
                )

                failure_record = None
                usage_record_error = None

                try:
                    failure_record = (
                        await run_in_threadpool(
                            persist_usage_only,
                            session_factory=(
                                get_session_factory()
                            ),
                            usage=NewUsageRecord(
                                caller_key_id=caller_key_id,
                                trace_id=trace_id,
                                conversation_id=(
                                    conversation_id
                                ),
                                request_kind=(
                                    "chat_stream"
                                ),
                                provider=(
                                    active_provider
                                ),
                                model=active_model,
                                status=(
                                    USAGE_STATUS_PROVIDER_FAILED
                                ),
                                usage_source=(
                                    failure_snapshot
                                    .usage_source
                                ),
                                prompt_tokens=(
                                    failure_snapshot
                                    .prompt_tokens
                                ),
                                completion_tokens=(
                                    failure_snapshot
                                    .completion_tokens
                                ),
                                total_tokens=(
                                    failure_snapshot
                                    .total_tokens
                                ),
                                latency_ms=(
                                    latency_ms
                                ),
                                error_type=(
                                    type(exc).__name__
                                ),
                            ),
                        )
                    )

                except Exception as usage_exc:
                    usage_record_error = str(
                        usage_exc
                    )

                err = build_error(
                    trace_id,
                    active_provider,
                    active_model,
                    latency_ms,
                    (
                        f"{active_provider} "
                        f"failed: {exc}"
                    ),
                )

                err[
                    "conversation_id"
                ] = conversation_id
                err[
                    "context_window"
                ] = context_window_payload
                err["prompt_id"] = (
                    prompt_id
                    or "none"
                )
                err["prompt_version"] = (
                    prompt_version
                    if prompt_id
                    else "none"
                )
                err["rag"] = {
                    **rag_dict,
                    "citations": [
                        (
                            citation.model_dump()
                            if hasattr(
                                citation,
                                "model_dump",
                            )
                            else citation
                        )
                        for citation
                        in citations
                    ],
                    "error": str(exc),
                }
                err["usage"] = (
                    build_usage_payload(
                        request_id=(
                            failure_record
                            .request_id
                            if failure_record
                            is not None
                            else None
                        ),
                        status=(
                            USAGE_STATUS_PROVIDER_FAILED
                        ),
                        snapshot=(
                            failure_snapshot
                        ),
                        cost_record=(
                            failure_record.usage_cost
                            if failure_record
                            is not None
                            else None
                        ),
                    )
                )

                if execution_payload is not None:
                    err[
                        "provider_execution"
                    ] = execution_payload

                if usage_record_error is not None:
                    err[
                        "usage_record_error"
                    ] = usage_record_error

                append_jsonl(
                    settings.RUN_LOG_PATH,
                    {
                        "trace_id": trace_id,
                        "conversation_id": (
                            conversation_id
                        ),
                        "mode": "stream",
                        "provider": (
                            active_provider
                        ),
                        "model": active_model,
                        "prompt_id": prompt_id,
                        "prompt_version": (
                            prompt_version
                            if prompt_id
                            else "none"
                        ),
                        "latency_ms": (
                            latency_ms
                        ),
                        "token_events": (
                            token_events
                        ),
                        "prompt_chars": (
                            len(system_text)
                            if system_text
                            else 0
                        ),
                        "output_chars": (
                            output_chars
                        ),
                        "temperature": (
                            body.temperature
                        ),
                        "top_p": body.top_p,
                        "max_tokens": (
                            body.max_tokens
                        ),
                        "rag_enabled": (
                            rag_enabled
                        ),
                        "kb_top_k": top_k,
                        "rag_hits": hits,
                        "context_chars": (
                            context_chars
                        ),
                        "rag_error": rag_error,
                        "usage_status": (
                            USAGE_STATUS_PROVIDER_FAILED
                        ),
                        "usage_source": (
                            failure_snapshot
                            .usage_source
                        ),
                        "error": str(exc),
                        "provider_execution": (
                            execution_payload
                        ),
                    },
                )

                yield sse_event(
                    "error",
                    err,
                )

                return

        finally:
            close_stream = getattr(
                stream_iterator,
                "aclose",
                None,
            )

            if callable(close_stream):
                try:
                    await close_stream()

                except asyncio.CancelledError:
                    raise

                except Exception:
                    # 清理失败不能覆盖 Provider 错误或客户端取消。
                    pass

        assistant_content = "".join(
            output_parts
        )

        latency_ms = int(
            (
                time.perf_counter()
                - start
            )
            * 1000
        )

        usage_snapshot = resolve_usage_snapshot(
            provider_usage=provider_usage,
            messages=provider_request.messages,
            completion_text=assistant_content,
        )

        success_usage = NewUsageRecord(
            caller_key_id=caller_key_id,
            trace_id=trace_id,
            conversation_id=conversation_id,
            request_kind="chat_stream",
            provider=active_provider,
            model=active_model,
            status=USAGE_STATUS_SUCCEEDED,
            usage_source=(
                usage_snapshot.usage_source
            ),
            prompt_tokens=(
                usage_snapshot.prompt_tokens
            ),
            completion_tokens=(
                usage_snapshot
                .completion_tokens
            ),
            total_tokens=(
                usage_snapshot.total_tokens
            ),
            latency_ms=latency_ms,
        )

        # Message.token_count 只保存 Provider 原生
        # completion token，不保存本地估算值。
        assistant_token_count = (
            usage_snapshot.completion_tokens
            if (
                usage_snapshot.usage_source
                == USAGE_SOURCE_PROVIDER_NATIVE
            )
            else None
        )

        persistence_task = asyncio.create_task(
            run_in_threadpool(
                persist_sync_exchange_and_usage,
                session_factory=(
                    get_session_factory()
                ),
                conversation_id=(
                    conversation_id
                ),
                request_messages=[
                    ContextMessage(
                        role=message.role,
                        content=message.content,
                    )
                    for message
                    in current_messages
                ],
                assistant_content=(
                    assistant_content
                ),
                provider=active_provider,
                model=active_model,
                assistant_token_count=(
                    assistant_token_count
                ),
                usage=success_usage,
            )
        )

        try:
            # Provider 已完整结束后，即使客户端此刻断开，
            # 也等待原子持久化完成，避免提交结果不确定。
            usage_result = await asyncio.shield(
                persistence_task
            )

        except (
            asyncio.CancelledError,
            GeneratorExit,
        ):
            try:
                await persistence_task
            except BaseException:
                pass

            raise

        except ConversationNotFoundError as exc:
            failure_record = None

            try:
                failure_record = (
                    await run_in_threadpool(
                        persist_usage_only,
                        session_factory=(
                            get_session_factory()
                        ),
                        usage=NewUsageRecord(
                            caller_key_id=caller_key_id,
                            trace_id=trace_id,
                            conversation_id=(
                                conversation_id
                            ),
                            request_kind=(
                                "chat_stream"
                            ),
                            provider=(
                                active_provider
                            ),
                            model=active_model,
                            status=(
                                USAGE_STATUS_PERSISTENCE_FAILED
                            ),
                            usage_source=(
                                usage_snapshot
                                .usage_source
                            ),
                            prompt_tokens=(
                                usage_snapshot
                                .prompt_tokens
                            ),
                            completion_tokens=(
                                usage_snapshot
                                .completion_tokens
                            ),
                            total_tokens=(
                                usage_snapshot
                                .total_tokens
                            ),
                            latency_ms=(
                                latency_ms
                            ),
                            error_type=(
                                "conversation_not_found"
                            ),
                        ),
                    )
                )

            except Exception:
                pass

            err = build_error(
                trace_id,
                active_provider,
                active_model,
                latency_ms,
                "Conversation not found",
            )
            err["conversation_id"] = (
                conversation_id
            )
            err["context_window"] = (
                context_window_payload
            )
            err["rag"] = {
                **rag_dict,
                "citations": [],
                "error": str(exc),
            }
            err["usage"] = build_usage_payload(
                request_id=(
                    failure_record.request_id
                    if failure_record
                    is not None
                    else None
                ),
                status=(
                    USAGE_STATUS_PERSISTENCE_FAILED
                ),
                snapshot=usage_snapshot,
                cost_record=(
                    failure_record.usage_cost
                    if failure_record
                    is not None
                    else None
                ),
            )

            yield sse_event(
                "error",
                err,
            )

            return

        except Exception as exc:
            failure_record = None
            usage_record_error = None

            try:
                failure_record = (
                    await run_in_threadpool(
                        persist_usage_only,
                        session_factory=(
                            get_session_factory()
                        ),
                        usage=NewUsageRecord(
                            caller_key_id=caller_key_id,
                            trace_id=trace_id,
                            conversation_id=(
                                conversation_id
                            ),
                            request_kind=(
                                "chat_stream"
                            ),
                            provider=(
                                active_provider
                            ),
                            model=active_model,
                            status=(
                                USAGE_STATUS_PERSISTENCE_FAILED
                            ),
                            usage_source=(
                                usage_snapshot
                                .usage_source
                            ),
                            prompt_tokens=(
                                usage_snapshot
                                .prompt_tokens
                            ),
                            completion_tokens=(
                                usage_snapshot
                                .completion_tokens
                            ),
                            total_tokens=(
                                usage_snapshot
                                .total_tokens
                            ),
                            latency_ms=(
                                latency_ms
                            ),
                            error_type=(
                                type(exc).__name__
                            ),
                        ),
                    )
                )

            except Exception as usage_exc:
                usage_record_error = str(
                    usage_exc
                )

            err = build_error(
                trace_id,
                active_provider,
                active_model,
                latency_ms,
                (
                    "conversation or usage "
                    f"persistence failed: {exc}"
                ),
            )
            err["conversation_id"] = (
                conversation_id
            )
            err["context_window"] = (
                context_window_payload
            )
            err["rag"] = {
                **rag_dict,
                "citations": [],
                "error": str(exc),
            }
            err["usage"] = build_usage_payload(
                request_id=(
                    failure_record.request_id
                    if failure_record
                    is not None
                    else None
                ),
                status=(
                    USAGE_STATUS_PERSISTENCE_FAILED
                ),
                snapshot=usage_snapshot,
                cost_record=(
                    failure_record.usage_cost
                    if failure_record
                    is not None
                    else None
                ),
            )

            if usage_record_error is not None:
                err[
                    "usage_record_error"
                ] = usage_record_error

            yield sse_event(
                "error",
                err,
            )

            return

        citations_payload = [
            (
                citation.model_dump()
                if hasattr(
                    citation,
                    "model_dump",
                )
                else citation
            )
            for citation in citations
        ]

        usage = {
            "trace_id": trace_id,
            "conversation_id": (
                conversation_id
            ),
            "provider": active_provider,
            "model": active_model,
            "latency_ms": latency_ms,
            "token_events": token_events,
            **build_usage_payload(
                request_id=(
                    usage_result.request_id
                ),
                status=(
                    USAGE_STATUS_SUCCEEDED
                ),
                snapshot=usage_snapshot,
                cost_record=(
                    usage_result.usage_cost
                ),
            ),
            "prompt_id": (
                prompt_id
                or "none"
            ),
            "prompt_version": (
                prompt_version
                if prompt_id
                else "none"
            ),
            "context_window": (
                context_window_payload
            ),
            "rag": {
                **rag_dict,
                "citations": (
                    citations_payload
                ),
                "error": (
                    rag_error
                    or rag_dict.get(
                        "error"
                    )
                ),
            },
            "provider_execution": execution_payload,
        }

        yield sse_event(
            "usage",
            usage,
        )

        yield sse_event(
            "done",
            "[DONE]",
        )

        append_jsonl(
            settings.RUN_LOG_PATH,
            {
                "trace_id": trace_id,
                "conversation_id": (
                    conversation_id
                ),
                "mode": "stream",
                "provider": active_provider,
                "model": active_model,
                "prompt_id": prompt_id,
                "prompt_version": (
                    prompt_version
                    if prompt_id
                    else "none"
                ),
                "latency_ms": latency_ms,
                "token_events": (
                    token_events
                ),
                "prompt_chars": (
                    len(system_text)
                    if system_text
                    else 0
                ),
                "output_chars": (
                    output_chars
                ),
                "rag_enabled": (
                    rag_enabled
                ),
                "kb_top_k": top_k,
                "rag_hits": hits,
                "context_chars": (
                    context_chars
                ),
                "rag_error": rag_error,
                "citations_count": (
                    len(citations)
                ),
                "provider_execution": (
                    execution_payload
                ),
            },
        )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
    )
