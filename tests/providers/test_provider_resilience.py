import asyncio

import pytest

from src.app.llm.providers import (
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderConnectionError,
    ProviderRequestError,
    ProviderRetryPolicy,
    ProviderStreamInterruptedError,
    ResilientChatProvider,
)


class ScriptedProvider:
    def __init__(
        self,
        name: str,
        *,
        chat_outcomes=(),
        stream_outcomes=(),
        default_model: str | None = None,
    ) -> None:
        self.name = name
        self.default_model = (
            default_model
            or f"{name}-default"
        )
        self.chat_outcomes = list(chat_outcomes)
        self.stream_outcomes = list(stream_outcomes)
        self.chat_requests = []
        self.stream_requests = []

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return requested_model or self.default_model

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        self.chat_requests.append(request)
        outcome = self.chat_outcomes.pop(0)

        if isinstance(outcome, BaseException):
            raise outcome

        return ProviderChatResponse(
            content=outcome,
            provider=self.name,
            model=self.resolve_model(request.model),
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ):
        self.stream_requests.append(request)
        outcome = self.stream_outcomes.pop(0)

        for item in outcome:
            if isinstance(item, BaseException):
                raise item

            yield ProviderChatChunk(
                delta=item,
                provider=self.name,
                model=self.resolve_model(request.model),
            )


def build_request(
    model: str | None = "primary-model",
) -> ProviderChatRequest:
    return ProviderChatRequest(
        messages=(),
        model=model,
    )


def test_sync_retries_retryable_failure():
    primary = ScriptedProvider(
        "primary",
        chat_outcomes=[
            ProviderConnectionError("down"),
            "ok",
        ],
    )
    delays = []
    provider = ResilientChatProvider(
        primary=primary,
        retry_policy=ProviderRetryPolicy(
            max_attempts=2,
            base_delay_ms=100,
            max_delay_ms=100,
        ),
        sync_sleep=delays.append,
    )

    response = provider.chat(build_request())

    assert response.content == "ok"
    assert len(primary.chat_requests) == 2
    assert delays == [0.1]
    assert response.execution is not None
    assert response.execution.retries == 1
    assert len(response.execution.attempts) == 2


def test_sync_does_not_retry_non_retryable_failure():
    error = ProviderRequestError("bad request")
    primary = ScriptedProvider(
        "primary",
        chat_outcomes=[error, "unused"],
    )
    provider = ResilientChatProvider(primary=primary)

    with pytest.raises(ProviderRequestError):
        provider.chat(build_request())

    assert len(primary.chat_requests) == 1
    assert error.execution is not None
    assert error.execution.retries == 0


def test_sync_falls_back_after_primary_exhaustion():
    primary = ScriptedProvider(
        "primary",
        chat_outcomes=[
            ProviderConnectionError("one"),
            ProviderConnectionError("two"),
        ],
    )
    fallback = ScriptedProvider(
        "fallback",
        chat_outcomes=["backup"],
    )
    provider = ResilientChatProvider(
        primary=primary,
        fallback=fallback,
        fallback_model="backup-model",
        retry_policy=ProviderRetryPolicy(
            max_attempts=2,
            base_delay_ms=0,
            max_delay_ms=0,
        ),
    )

    response = provider.chat(build_request())

    assert response.content == "backup"
    assert response.provider == "fallback"
    assert fallback.chat_requests[0].model == "backup-model"
    assert response.execution is not None
    assert response.execution.fallback_used is True
    assert len(response.execution.attempts) == 3


def test_stream_retries_before_first_non_empty_token():
    primary = ScriptedProvider(
        "primary",
        stream_outcomes=[
            [
                "",
                ProviderConnectionError("before token"),
            ],
            ["ok"],
        ],
    )
    provider = ResilientChatProvider(
        primary=primary,
        retry_policy=ProviderRetryPolicy(
            max_attempts=2,
            base_delay_ms=0,
            max_delay_ms=0,
        ),
    )

    async def collect():
        return [
            chunk
            async for chunk in provider.stream(
                build_request()
            )
        ]

    chunks = asyncio.run(collect())
    execution = next(
        chunk.execution
        for chunk in reversed(chunks)
        if chunk.execution is not None
    )

    assert "".join(chunk.delta for chunk in chunks) == "ok"
    assert len(primary.stream_requests) == 2
    assert execution.retries == 1


def test_stream_never_retries_after_output_started():
    primary = ScriptedProvider(
        "primary",
        stream_outcomes=[
            [
                "a",
                ProviderConnectionError("after token"),
            ],
        ],
    )
    fallback = ScriptedProvider(
        "fallback",
        stream_outcomes=[["backup"]],
    )
    provider = ResilientChatProvider(
        primary=primary,
        fallback=fallback,
        retry_policy=ProviderRetryPolicy(
            max_attempts=2,
            base_delay_ms=0,
            max_delay_ms=0,
        ),
    )

    async def collect():
        return [
            chunk
            async for chunk in provider.stream(
                build_request()
            )
        ]

    with pytest.raises(
        ProviderStreamInterruptedError
    ) as captured:
        asyncio.run(collect())

    assert len(primary.stream_requests) == 1
    assert fallback.stream_requests == []
    assert captured.value.execution is not None
    assert (
        captured.value.execution.attempts[-1].outcome
        == "stream_interrupted"
    )
