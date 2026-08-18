from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi.responses import StreamingResponse

from src.app.db.session import SessionFactory
from src.app.llm.providers import (
    ChatProvider,
    ChatProviderError,
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderUsage,
    provider_execution_payload,
    provider_execution_target,
)
from src.app.services import (
    USAGE_STATUS_CLIENT_DISCONNECTED,
    USAGE_STATUS_PROVIDER_FAILED,
    USAGE_STATUS_SUCCEEDED,
)
from src.app.usage import (
    resolve_terminal_usage_snapshot,
    resolve_usage_snapshot,
)

from .schemas import (
    OpenAIChatCompletionChunk,
    OpenAIChatCompletionChunkChoice,
    OpenAIChatCompletionDelta,
    OpenAICompletionUsage,
    OpenAIErrorDetail,
    OpenAIErrorResponse,
    OpenAIGatewayMetadata,
)
from .usage_accounting import (
    OPENAI_STREAM_REQUEST_KIND,
    persist_openai_usage,
)


def _completion_id() -> str:
    return f"chatcmpl-{uuid4().hex}"


def _sse_data(
    payload: dict | str,
) -> str:
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
    if usage is None:
        return None

    prompt_tokens = usage.prompt_tokens
    completion_tokens = (
        usage.completion_tokens
    )
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

    if (
        prompt_tokens is None
        or completion_tokens is None
        or total_tokens is None
    ):
        return None

    return OpenAICompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=(
            completion_tokens
        ),
        total_tokens=total_tokens,
    )


def _serialize_chunk(
    chunk: OpenAIChatCompletionChunk,
) -> str:
    payload = chunk.model_dump(
        exclude_none=True,
    )

    for choice in payload.get(
        "choices",
        [],
    ):
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
                    delta=(
                        OpenAIChatCompletionDelta(
                            role="assistant",
                        )
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
                    delta=(
                        OpenAIChatCompletionDelta(
                            content=content,
                        )
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
    provider_execution: dict | None = None,
) -> str:
    return _serialize_chunk(
        OpenAIChatCompletionChunk(
            id=completion_id,
            created=created,
            model=model,
            choices=[
                OpenAIChatCompletionChunkChoice(
                    index=0,
                    delta=(
                        OpenAIChatCompletionDelta()
                    ),
                    finish_reason=(
                        finish_reason
                    ),
                    logprobs=None,
                )
            ],
            gateway=(
                OpenAIGatewayMetadata(
                    provider_execution=(
                        provider_execution
                    )
                )
                if provider_execution is not None
                else None
            ),
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
    error_type: str = "api_error",
    code: str = "provider_error",
    provider_execution: dict | None = None,
) -> str:
    response = OpenAIErrorResponse(
        error=OpenAIErrorDetail(
            message=message,
            type=error_type,
            param=None,
            code=code,
        ),
        gateway=(
            OpenAIGatewayMetadata(
                provider_execution=(
                    provider_execution
                )
            )
            if provider_execution is not None
            else None
        ),
    )

    payload = response.model_dump()

    if response.gateway is None:
        payload.pop("gateway", None)

    return _sse_data(payload)


def _latency_ms(
    started_at: float,
) -> int:
    return int(
        (
            time.perf_counter()
            - started_at
        )
        * 1000
    )


async def _stream_events(
    *,
    provider: ChatProvider,
    request: ProviderChatRequest,
    requested_model: str,
    include_usage: bool,
    session_factory: SessionFactory,
    trace_id: str,
    caller_key_id: str | None,
) -> AsyncIterator[str]:
    completion_id = _completion_id()
    created = int(time.time())
    started_at = time.perf_counter()

    iterator = None
    terminal_handled = False

    active_provider = provider.name
    active_model = (
        requested_model
        or "unknown"
    )

    latest_usage: ProviderUsage | None = None
    execution_payload = None
    completion_parts: list[str] = []
    finish_reason: str | None = None

    try:
        try:
            resolved_model = (
                provider.resolve_model(
                    requested_model
                )
                or requested_model
                or "unknown"
            )

        except Exception:
            resolved_model = (
                requested_model
                or "unknown"
            )

        active_model = resolved_model

        iterator = provider.stream(
            request
        ).__aiter__()

        try:
            first_chunk = await anext(
                iterator
            )

        except StopAsyncIteration:
            first_chunk = None

        if first_chunk is not None:
            active_provider = (
                first_chunk.provider
                or active_provider
            )
            active_model = (
                first_chunk.model
                or active_model
            )
            if first_chunk.execution is not None:
                execution_payload = (
                    provider_execution_payload(
                        first_chunk.execution
                    )
                )
                active_provider, active_model = (
                    provider_execution_target(
                        first_chunk.execution,
                        provider=active_provider,
                        model=active_model,
                    )
                )

        yield _role_chunk(
            completion_id=completion_id,
            created=created,
            model=active_model,
        )

        async def all_chunks(
        ) -> AsyncIterator[
            ProviderChatChunk
        ]:
            if first_chunk is not None:
                yield first_chunk

            assert iterator is not None

            async for item in iterator:
                yield item

        async for chunk in all_chunks():
            active_provider = (
                chunk.provider
                or active_provider
            )
            active_model = (
                chunk.model
                or active_model
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

            if chunk.delta != "":
                completion_parts.append(
                    chunk.delta
                )

                yield _content_chunk(
                    completion_id=(
                        completion_id
                    ),
                    created=created,
                    model=active_model,
                    content=chunk.delta,
                )

            if chunk.usage is not None:
                latest_usage = chunk.usage

            if (
                chunk.finish_reason
                is not None
            ):
                finish_reason = (
                    chunk.finish_reason
                )

        completion_text = "".join(
            completion_parts
        )

        usage_snapshot = (
            resolve_usage_snapshot(
                provider_usage=(
                    latest_usage
                ),
                messages=request.messages,
                completion_text=(
                    completion_text
                ),
            )
        )

        try:
            persist_openai_usage(
                session_factory=(
                    session_factory
                ),
                trace_id=trace_id,
                caller_key_id=(
                    caller_key_id
                ),
                request_kind=(
                    OPENAI_STREAM_REQUEST_KIND
                ),
                provider=active_provider,
                model=active_model,
                status=(
                    USAGE_STATUS_SUCCEEDED
                ),
                snapshot=usage_snapshot,
                latency_ms=_latency_ms(
                    started_at
                ),
            )

        except Exception as exc:
            terminal_handled = True

            yield _error_event(
                message=(
                    "Usage persistence "
                    f"failed: {exc}"
                ),
                error_type="server_error",
                code=(
                    "usage_persistence_error"
                ),
                provider_execution=(
                    execution_payload
                ),
            )
            return

        terminal_handled = True

        yield _finish_chunk(
            completion_id=completion_id,
            created=created,
            model=active_model,
            finish_reason=(
                finish_reason
                or "stop"
            ),
            provider_execution=(
                execution_payload
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
                completion_id=(
                    completion_id
                ),
                created=created,
                model=active_model,
                usage=mapped_usage,
            )

        yield _sse_data("[DONE]")

    except ChatProviderError as exc:
        execution = exc.execution

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

        completion_text = "".join(
            completion_parts
        )

        snapshot = (
            resolve_terminal_usage_snapshot(
                provider_usage=(
                    latest_usage
                ),
                messages=request.messages,
                completion_text=(
                    completion_text
                ),
            )
        )

        accounting_error = None

        try:
            persist_openai_usage(
                session_factory=(
                    session_factory
                ),
                trace_id=trace_id,
                caller_key_id=(
                    caller_key_id
                ),
                request_kind=(
                    OPENAI_STREAM_REQUEST_KIND
                ),
                provider=active_provider,
                model=active_model,
                status=(
                    USAGE_STATUS_PROVIDER_FAILED
                ),
                snapshot=snapshot,
                latency_ms=_latency_ms(
                    started_at
                ),
                error_type=(
                    type(exc).__name__
                ),
            )

        except Exception as usage_exc:
            accounting_error = str(
                usage_exc
            )

        terminal_handled = True

        message = str(exc)

        if accounting_error is not None:
            message += (
                "; usage persistence "
                f"failed: {accounting_error}"
            )

        yield _error_event(
            message=message,
            provider_execution=(
                execution_payload
            ),
        )

    except (
        asyncio.CancelledError,
        GeneratorExit,
    ):
        if not terminal_handled:
            completion_text = "".join(
                completion_parts
            )

            snapshot = (
                resolve_terminal_usage_snapshot(
                    provider_usage=(
                        latest_usage
                    ),
                    messages=(
                        request.messages
                    ),
                    completion_text=(
                        completion_text
                    ),
                )
            )

            try:
                persist_openai_usage(
                    session_factory=(
                        session_factory
                    ),
                    trace_id=trace_id,
                    caller_key_id=(
                        caller_key_id
                    ),
                    request_kind=(
                        OPENAI_STREAM_REQUEST_KIND
                    ),
                    provider=active_provider,
                    model=active_model,
                    status=(
                        USAGE_STATUS_CLIENT_DISCONNECTED
                    ),
                    snapshot=snapshot,
                    latency_ms=_latency_ms(
                        started_at
                    ),
                    error_type=(
                        "client_disconnected"
                    ),
                )

            except Exception:
                pass

            terminal_handled = True

        raise

    except Exception as exc:
        completion_text = "".join(
            completion_parts
        )

        snapshot = (
            resolve_terminal_usage_snapshot(
                provider_usage=(
                    latest_usage
                ),
                messages=request.messages,
                completion_text=(
                    completion_text
                ),
            )
        )

        accounting_error = None

        try:
            persist_openai_usage(
                session_factory=(
                    session_factory
                ),
                trace_id=trace_id,
                caller_key_id=(
                    caller_key_id
                ),
                request_kind=(
                    OPENAI_STREAM_REQUEST_KIND
                ),
                provider=active_provider,
                model=active_model,
                status=(
                    USAGE_STATUS_PROVIDER_FAILED
                ),
                snapshot=snapshot,
                latency_ms=_latency_ms(
                    started_at
                ),
                error_type=(
                    type(exc).__name__
                ),
            )

        except Exception as usage_exc:
            accounting_error = str(
                usage_exc
            )

        terminal_handled = True

        message = (
            f"{provider.name} provider "
            f"failed: {exc}"
        )

        if accounting_error is not None:
            message += (
                "; usage persistence "
                f"failed: {accounting_error}"
            )

        yield _error_event(
            message=message,
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
                    pass


def build_openai_streaming_response(
    *,
    provider: ChatProvider,
    request: ProviderChatRequest,
    requested_model: str,
    include_usage: bool,
    session_factory: SessionFactory,
    trace_id: str,
    caller_key_id: str | None,
) -> StreamingResponse:
    return StreamingResponse(
        _stream_events(
            provider=provider,
            request=request,
            requested_model=(
                requested_model
            ),
            include_usage=include_usage,
            session_factory=(
                session_factory
            ),
            trace_id=trace_id,
            caller_key_id=(
                caller_key_id
            ),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
