from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi.responses import StreamingResponse

from src.app.llm.providers import (
    ChatProvider,
    ChatProviderError,
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderUsage,
)

from .schemas import (
    OpenAIChatCompletionChunk,
    OpenAIChatCompletionChunkChoice,
    OpenAIChatCompletionDelta,
    OpenAICompletionUsage,
    OpenAIErrorDetail,
    OpenAIErrorResponse,
)


def _completion_id() -> str:
    return f"chatcmpl-{uuid4().hex}"


def _sse_data(
    payload: dict | str,
) -> str:
    """Serialize one OpenAI-compatible SSE data block."""

    if isinstance(payload, str):
        data = payload
    else:
        data = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    return f"data: {data}\n\n"


def _map_usage(
    usage: ProviderUsage | None,
) -> OpenAICompletionUsage | None:
    """Map complete Provider usage to OpenAI usage."""

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

    # 未知用量不能使用零值伪造。
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


def _serialize_chunk(
    chunk: OpenAIChatCompletionChunk,
) -> str:
    """Serialize a chunk while retaining required null fields."""

    payload = chunk.model_dump(
        exclude_none=True,
    )

    for choice in payload.get("choices", []):
        # OpenAI streaming choices explicitly expose these
        # fields even when the current value is null.
        choice.setdefault(
            "finish_reason",
            None,
        )
        choice["logprobs"] = None

    return _sse_data(payload)


def _role_chunk(
    *,
    completion_id: str,
    created: int,
    model: str,
) -> str:
    return _serialize_chunk(
        OpenAIChatCompletionChunk(
            id=completion_id,
            created=created,
            model=model,
            choices=[
                OpenAIChatCompletionChunkChoice(
                    index=0,
                    delta=OpenAIChatCompletionDelta(
                        role="assistant",
                    ),
                    finish_reason=None,
                    logprobs=None,
                )
            ],
        )
    )


def _content_chunk(
    *,
    completion_id: str,
    created: int,
    model: str,
    content: str,
) -> str:
    return _serialize_chunk(
        OpenAIChatCompletionChunk(
            id=completion_id,
            created=created,
            model=model,
            choices=[
                OpenAIChatCompletionChunkChoice(
                    index=0,
                    delta=OpenAIChatCompletionDelta(
                        content=content,
                    ),
                    finish_reason=None,
                    logprobs=None,
                )
            ],
        )
    )


def _finish_chunk(
    *,
    completion_id: str,
    created: int,
    model: str,
    finish_reason: str,
) -> str:
    return _serialize_chunk(
        OpenAIChatCompletionChunk(
            id=completion_id,
            created=created,
            model=model,
            choices=[
                OpenAIChatCompletionChunkChoice(
                    index=0,
                    delta=OpenAIChatCompletionDelta(),
                    finish_reason=finish_reason,
                    logprobs=None,
                )
            ],
        )
    )


def _usage_chunk(
    *,
    completion_id: str,
    created: int,
    model: str,
    usage: OpenAICompletionUsage,
) -> str:
    return _serialize_chunk(
        OpenAIChatCompletionChunk(
            id=completion_id,
            created=created,
            model=model,
            choices=[],
            usage=usage,
        )
    )


def _error_event(
    *,
    message: str,
) -> str:
    payload = OpenAIErrorResponse(
        error=OpenAIErrorDetail(
            message=message,
            type="api_error",
            param=None,
            code="provider_error",
        )
    ).model_dump()

    return _sse_data(payload)


async def _stream_events(
    *,
    provider: ChatProvider,
    request: ProviderChatRequest,
    requested_model: str,
    include_usage: bool,
) -> AsyncIterator[str]:
    """Adapt Provider chunks to OpenAI Chat Completion SSE."""

    completion_id = _completion_id()
    created = int(time.time())

    iterator = None

    try:
        resolved_model = (
            provider.resolve_model(requested_model)
            or requested_model
            or "unknown"
        )

        iterator = provider.stream(
            request
        ).__aiter__()

        # 先读取首个 Provider chunk：
        # 1. 能获得 Provider 实际模型名；
        # 2. Provider 在第一次迭代就失败时，只输出 error，
        #    不会先产生一个虚假的 assistant role。
        try:
            first_chunk = await anext(iterator)
        except StopAsyncIteration:
            first_chunk = None

        active_model = (
            first_chunk.model
            if (
                first_chunk is not None
                and first_chunk.model
            )
            else resolved_model
        )

        # OpenAI-compatible 首个正常 chunk 建立角色。
        yield _role_chunk(
            completion_id=completion_id,
            created=created,
            model=active_model,
        )

        finish_reason: str | None = None
        latest_usage: ProviderUsage | None = None

        async def all_chunks() -> AsyncIterator[
            ProviderChatChunk
        ]:
            if first_chunk is not None:
                yield first_chunk

            assert iterator is not None

            async for item in iterator:
                yield item

        async for chunk in all_chunks():
            # 只跳过真正的空字符串；单空格是合法 token。
            if chunk.delta != "":
                yield _content_chunk(
                    completion_id=completion_id,
                    created=created,
                    model=active_model,
                    content=chunk.delta,
                )

            if chunk.usage is not None:
                latest_usage = chunk.usage

            if chunk.finish_reason is not None:
                finish_reason = chunk.finish_reason

        # MockProvider 不主动产生 terminal chunk，
        # 因此成功耗尽时统一补 stop。
        yield _finish_chunk(
            completion_id=completion_id,
            created=created,
            model=active_model,
            finish_reason=(
                finish_reason
                or "stop"
            ),
        )

        mapped_usage = _map_usage(
            latest_usage
        )

        if (
            include_usage
            and mapped_usage is not None
        ):
            yield _usage_chunk(
                completion_id=completion_id,
                created=created,
                model=active_model,
                usage=mapped_usage,
            )

        yield _sse_data("[DONE]")

    except ChatProviderError as exc:
        # StreamingResponse 已建立，不能再改成 HTTP 502；
        # 通过可解析的 SSE data error 传递业务失败。
        yield _error_event(
            message=str(exc),
        )

    except Exception as exc:
        yield _error_event(
            message=(
                f"{provider.name} provider failed: "
                f"{exc}"
            ),
        )

    finally:
        if iterator is not None:
            close = getattr(
                iterator,
                "aclose",
                None,
            )

            if callable(close):
                try:
                    await close()
                except Exception:
                    # 清理失败不能覆盖已经输出的流式结果。
                    pass


def build_openai_streaming_response(
    *,
    provider: ChatProvider,
    request: ProviderChatRequest,
    requested_model: str,
    include_usage: bool,
) -> StreamingResponse:
    return StreamingResponse(
        _stream_events(
            provider=provider,
            request=request,
            requested_model=requested_model,
            include_usage=include_usage,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
