from __future__ import annotations

import time
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.app.core.settings import settings
from src.app.core.logging import get_trace_id
from src.app.db.session import (
    get_session_factory,
)
from src.app.services import (
    USAGE_STATUS_PROVIDER_FAILED,
    USAGE_STATUS_SUCCEEDED,
)
from src.app.usage import (
    resolve_usage_snapshot,
    unavailable_usage_snapshot,
)
from src.app.llm.providers import (
    ChatProviderError,
    ProviderChatResponse,
    ProviderUsage,
    UnsupportedProviderError,
    build_provider_request,
    get_chat_provider,
)

from .errors import openai_error_response
from .route import OpenAICompatRoute
from .streaming import (
    build_openai_streaming_response,
)
from .usage_accounting import (
    OPENAI_SYNC_REQUEST_KIND,
    caller_key_id_from_request,
    persist_openai_usage,
)
from .schemas import (
    OpenAIAssistantMessage,
    OpenAIChatCompletionChoice,
    OpenAIChatCompletionRequest,
    OpenAIChatCompletionResponse,
    OpenAICompletionUsage,
    OpenAIErrorResponse,
)


router = APIRouter(
    prefix="/v1",
    tags=["OpenAI Compatibility"],
    route_class=OpenAICompatRoute,
)


def _completion_id() -> str:
    return f"chatcmpl-{uuid4().hex}"


def _map_usage(
    usage: ProviderUsage | None,
) -> OpenAICompletionUsage | None:
    if usage is None:
        return None

    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    total_tokens = usage.total_tokens

    if (
        total_tokens is None
        and prompt_tokens is not None
        and completion_tokens is not None
    ):
        total_tokens = (
            prompt_tokens
            + completion_tokens
        )

    # 不使用零值伪造未知 token 数量。
    if (
        prompt_tokens is None
        or completion_tokens is None
        or total_tokens is None
    ):
        return None

    return OpenAICompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _build_response(
    provider_response: ProviderChatResponse,
    *,
    requested_model: str,
) -> OpenAIChatCompletionResponse:
    return OpenAIChatCompletionResponse(
        id=_completion_id(),
        created=int(time.time()),
        model=(
            provider_response.model
            or requested_model
        ),
        choices=[
            OpenAIChatCompletionChoice(
                index=0,
                message=OpenAIAssistantMessage(
                    content=provider_response.content,
                ),
                finish_reason=(
                    provider_response.finish_reason
                    or "stop"
                ),
                logprobs=None,
            )
        ],
        usage=_map_usage(provider_response.usage),
    )


def _completion_json_response(
    response: OpenAIChatCompletionResponse,
) -> JSONResponse:
    """序列化非流式 Chat Completion。

    未知 usage 继续省略，但 OpenAI-compatible choice 中的
    logprobs 字段应显式保留为 null。
    """

    payload = response.model_dump(
        exclude_none=True,
    )

    for choice in payload.get("choices", []):
        choice["logprobs"] = None

    return JSONResponse(
        status_code=200,
        content=payload,
    )


@router.post(
    "/chat/completions",
    response_model=OpenAIChatCompletionResponse,
    response_model_exclude_none=True,
    summary="Create chat completion",
    description=(
        "OpenAI-compatible Chat Completions endpoint. "
        "Supports non-streaming chat.completion responses "
        "and streaming chat.completion.chunk SSE responses."
    ),
    responses={
        400: {
            "model": OpenAIErrorResponse,
            "description": "Invalid or unsupported request.",
        },
        500: {
            "model": OpenAIErrorResponse,
            "description": "Gateway configuration error.",
        },
        502: {
            "model": OpenAIErrorResponse,
            "description": "Downstream provider error.",
        },
    },
)
def create_chat_completion(
    request: Request,
    body: OpenAIChatCompletionRequest,
):
    if body.n != 1:
        return openai_error_response(
            status_code=400,
            message="Only n=1 is currently supported.",
            error_type="invalid_request_error",
            param="n",
            code="unsupported_value",
        )

    provider_name = (
        body.provider
        or settings.OPENAI_COMPAT_DEFAULT_PROVIDER
    )

    try:
        provider = get_chat_provider(provider_name)
    except UnsupportedProviderError as exc:
        # 请求 provider 已由 Schema 约束，因此这里通常代表
        # OPENAI_COMPAT_DEFAULT_PROVIDER 服务端配置错误。
        return openai_error_response(
            status_code=500,
            message=str(exc),
            error_type="server_error",
            code="invalid_gateway_configuration",
        )

    trace_id = get_trace_id(request)
    caller_key_id = (
        caller_key_id_from_request(
            request
        )
    )

    try:
        resolved_model = (
            provider.resolve_model(
                body.model
            )
            or body.model
            or "unknown"
        )

    except Exception:
        resolved_model = (
            body.model
            or "unknown"
        )

    provider_request = build_provider_request(
        body.messages,
        model=body.model,
        temperature=(
            body.temperature
            if body.temperature is not None
            else 1.0
        ),
        top_p=(
            body.top_p
            if body.top_p is not None
            else 1.0
        ),
        max_tokens=body.resolved_max_tokens(),
    )

    if body.stream:
        return build_openai_streaming_response(
            provider=provider,
            request=provider_request,
            requested_model=body.model,
            include_usage=bool(
                body.stream_options
                and body.stream_options.include_usage
            ),
            session_factory=(
                get_session_factory()
            ),
            trace_id=trace_id,
            caller_key_id=caller_key_id,
        )

    started_at = time.perf_counter()

    try:
        provider_response = provider.chat(
            provider_request
        )

    except ChatProviderError as exc:
        latency_ms = int(
            (
                time.perf_counter()
                - started_at
            )
            * 1000
        )

        try:
            persist_openai_usage(
                session_factory=(
                    get_session_factory()
                ),
                trace_id=trace_id,
                caller_key_id=caller_key_id,
                request_kind=(
                    OPENAI_SYNC_REQUEST_KIND
                ),
                provider=provider.name,
                model=resolved_model,
                status=(
                    USAGE_STATUS_PROVIDER_FAILED
                ),
                snapshot=(
                    unavailable_usage_snapshot()
                ),
                latency_ms=latency_ms,
                error_type=(
                    type(exc).__name__
                ),
            )

        except Exception:
            # Accounting failure must not hide
            # the original Provider error.
            pass

        return openai_error_response(
            status_code=502,
            message=str(exc),
            error_type="api_error",
            code="provider_error",
        )

    except Exception as exc:
        latency_ms = int(
            (
                time.perf_counter()
                - started_at
            )
            * 1000
        )

        try:
            persist_openai_usage(
                session_factory=(
                    get_session_factory()
                ),
                trace_id=trace_id,
                caller_key_id=caller_key_id,
                request_kind=(
                    OPENAI_SYNC_REQUEST_KIND
                ),
                provider=provider.name,
                model=resolved_model,
                status=(
                    USAGE_STATUS_PROVIDER_FAILED
                ),
                snapshot=(
                    unavailable_usage_snapshot()
                ),
                latency_ms=latency_ms,
                error_type=(
                    type(exc).__name__
                ),
            )

        except Exception:
            pass

        return openai_error_response(
            status_code=502,
            message=(
                f"{provider.name} provider failed: "
                f"{exc}"
            ),
            error_type="api_error",
            code="provider_error",
        )

    latency_ms = int(
        (
            time.perf_counter()
            - started_at
        )
        * 1000
    )

    active_provider = (
        provider_response.provider
        or provider.name
    )
    active_model = (
        provider_response.model
        or resolved_model
    )

    usage_snapshot = resolve_usage_snapshot(
        provider_usage=(
            provider_response.usage
        ),
        messages=provider_request.messages,
        completion_text=(
            provider_response.content
        ),
    )

    try:
        persist_openai_usage(
            session_factory=(
                get_session_factory()
            ),
            trace_id=trace_id,
            caller_key_id=caller_key_id,
            request_kind=(
                OPENAI_SYNC_REQUEST_KIND
            ),
            provider=active_provider,
            model=active_model,
            status=USAGE_STATUS_SUCCEEDED,
            snapshot=usage_snapshot,
            latency_ms=latency_ms,
        )

    except Exception as exc:
        return openai_error_response(
            status_code=500,
            message=(
                "Usage persistence failed: "
                f"{exc}"
            ),
            error_type="server_error",
            code="usage_persistence_error",
        )

    completion = _build_response(
        provider_response,
        requested_model=body.model,
    )

    return _completion_json_response(completion)
