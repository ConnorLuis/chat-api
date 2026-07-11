from __future__ import annotations

import json
from collections.abc import AsyncIterator

from src.app.api.openai_compat import (
    routes_chat_completions as routes_module,
)
from src.app.llm.providers import (
    ChatProviderError,
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderUsage,
)


def parse_sse_data(body: str) -> list[str]:
    """Parse data-only SSE without stripping payload content."""

    normalized = body.replace(
        "\r\n",
        "\n",
    )

    events: list[str] = []

    for block in normalized.split("\n\n"):
        block = block.strip("\n")

        if not block:
            continue

        data_lines: list[str] = []

        for line in block.split("\n"):
            if not line.startswith("data:"):
                continue

            value = line[len("data:"):]

            # 只移除冒号后的一个可选 SSE 分隔空格。
            if value.startswith(" "):
                value = value[1:]

            data_lines.append(value)

        if data_lines:
            events.append(
                "\n".join(data_lines)
            )

    return events


def json_chunks(
    events: list[str],
) -> list[dict]:
    return [
        json.loads(event)
        for event in events
        if event != "[DONE]"
    ]


class StaticStreamingProvider:
    name = "fake"

    def __init__(
        self,
        chunks: list[ProviderChatChunk],
    ) -> None:
        self.chunks = chunks
        self.requests: list[
            ProviderChatRequest
        ] = []

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return requested_model or "fake-default-model"

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        raise AssertionError(
            "chat() must not be used for stream=true"
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        self.requests.append(request)

        for chunk in self.chunks:
            yield chunk


class FailingStreamingProvider:
    name = "failing"

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return requested_model or "failing-model"

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        raise AssertionError(
            "chat() must not be used for stream=true"
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        yield ProviderChatChunk(
            delta="partial",
            provider=self.name,
            model="failing-model",
        )

        raise ChatProviderError(
            "stream exploded"
        )


def test_mock_stream_returns_openai_chunks(
    client,
):
    response = client.post(
        "/v1/chat/completions",
        json={
            "provider": "mock",
            "model": "mock-stream-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello stream",
                }
            ],
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert response.headers[
        "content-type"
    ].startswith("text/event-stream")

    body = response.text

    # OpenAI-compatible SSE 只使用 data:，
    # 不能泄漏旧项目的 event: meta/token。
    assert "event: meta" not in body
    assert "event: token" not in body

    events = parse_sse_data(body)

    assert events[-1] == "[DONE]"

    chunks = json_chunks(events)

    assert chunks[0]["choices"][0]["delta"] == {
        "role": "assistant",
    }

    reconstructed = "".join(
        chunk["choices"][0]["delta"].get(
            "content",
            "",
        )
        for chunk in chunks
        if chunk["choices"]
    )

    assert reconstructed == (
        "[mock-stream] "
        "[mock] you said: hello stream"
    )

    finish_chunks = [
        chunk
        for chunk in chunks
        if (
            chunk["choices"]
            and chunk["choices"][0][
                "finish_reason"
            ] is not None
        )
    ]

    assert len(finish_chunks) == 1
    assert finish_chunks[0]["choices"][0][
        "finish_reason"
    ] == "stop"
    assert finish_chunks[0]["choices"][0][
        "delta"
    ] == {}

    assert not any(
        "usage" in chunk
        for chunk in chunks
    )

    assert {
        chunk["object"]
        for chunk in chunks
    } == {
        "chat.completion.chunk",
    }

    assert len({
        chunk["id"]
        for chunk in chunks
    }) == 1

    assert len({
        chunk["created"]
        for chunk in chunks
    }) == 1

    assert {
        chunk["model"]
        for chunk in chunks
    } == {
        "mock-stream-model",
    }


def test_stream_provider_override_and_usage(
    client,
    monkeypatch,
):
    provider = StaticStreamingProvider(
        chunks=[
            ProviderChatChunk(
                delta="hello",
                provider="fake",
                model="actual-stream-model",
            ),
            ProviderChatChunk(
                delta=" ",
                provider="fake",
                model="actual-stream-model",
            ),
            ProviderChatChunk(
                delta="world",
                provider="fake",
                model="actual-stream-model",
            ),
            ProviderChatChunk(
                delta="",
                provider="fake",
                model="actual-stream-model",
                finish_reason="length",
                usage=ProviderUsage(
                    prompt_tokens=8,
                    completion_tokens=3,
                    total_tokens=11,
                ),
            ),
        ]
    )

    captured_names: list[str] = []

    def fake_factory(
        provider_name: str,
    ):
        captured_names.append(provider_name)
        return provider

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        fake_factory,
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "provider": "ollama",
            "model": "requested-model",
            "messages": [
                {
                    "role": "system",
                    "content": "be concise",
                },
                {
                    "role": "user",
                    "content": "hello",
                },
            ],
            "temperature": 0.2,
            "top_p": 0.8,
            "max_completion_tokens": 64,
            "stream": True,
            "stream_options": {
                "include_usage": True,
            },
        },
    )

    assert response.status_code == 200
    assert captured_names == ["ollama"]

    provider_request = provider.requests[0]

    assert provider_request.model == "requested-model"
    assert provider_request.temperature == 0.2
    assert provider_request.top_p == 0.8
    assert provider_request.max_tokens == 64

    events = parse_sse_data(
        response.text
    )
    chunks = json_chunks(events)

    assert events[-1] == "[DONE]"

    assert {
        chunk["model"]
        for chunk in chunks
    } == {
        "actual-stream-model",
    }

    reconstructed = "".join(
        chunk["choices"][0]["delta"].get(
            "content",
            "",
        )
        for chunk in chunks
        if chunk["choices"]
    )

    assert reconstructed == "hello world"

    finish_chunks = [
        chunk
        for chunk in chunks
        if (
            chunk["choices"]
            and chunk["choices"][0][
                "finish_reason"
            ] is not None
        )
    ]

    assert finish_chunks[0]["choices"][0][
        "finish_reason"
    ] == "length"

    usage_chunks = [
        chunk
        for chunk in chunks
        if not chunk["choices"]
    ]

    assert len(usage_chunks) == 1
    assert usage_chunks[0]["usage"] == {
        "prompt_tokens": 8,
        "completion_tokens": 3,
        "total_tokens": 11,
    }


def test_include_usage_false_suppresses_usage_chunk(
    client,
    monkeypatch,
):
    provider = StaticStreamingProvider(
        chunks=[
            ProviderChatChunk(
                delta="ok",
                provider="fake",
                model="fake-model",
            ),
            ProviderChatChunk(
                delta="",
                provider="fake",
                model="fake-model",
                finish_reason="stop",
                usage=ProviderUsage(
                    prompt_tokens=2,
                    completion_tokens=1,
                    total_tokens=3,
                ),
            ),
        ]
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "fake-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
            "stream": True,
        },
    )

    chunks = json_chunks(
        parse_sse_data(response.text)
    )

    assert not any(
        not chunk["choices"]
        for chunk in chunks
    )


def test_incomplete_usage_is_not_fabricated(
    client,
    monkeypatch,
):
    provider = StaticStreamingProvider(
        chunks=[
            ProviderChatChunk(
                delta="ok",
                provider="fake",
                model="fake-model",
            ),
            ProviderChatChunk(
                delta="",
                provider="fake",
                model="fake-model",
                finish_reason="stop",
                usage=ProviderUsage(
                    prompt_tokens=2,
                    completion_tokens=None,
                    total_tokens=None,
                ),
            ),
        ]
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "fake-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
            "stream": True,
            "stream_options": {
                "include_usage": True,
            },
        },
    )

    chunks = json_chunks(
        parse_sse_data(response.text)
    )

    assert not any(
        not chunk["choices"]
        for chunk in chunks
    )


def test_provider_failure_emits_error_without_done(
    client,
    monkeypatch,
):
    provider = FailingStreamingProvider()

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "failing-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
            "stream": True,
        },
    )

    assert response.status_code == 200

    events = parse_sse_data(
        response.text
    )

    assert "[DONE]" not in events

    error = json.loads(
        events[-1]
    )["error"]

    assert error["type"] == "api_error"
    assert error["code"] == "provider_error"
    assert "stream exploded" in error["message"]

    chunks = [
        json.loads(event)
        for event in events[:-1]
    ]

    reconstructed = "".join(
        chunk["choices"][0]["delta"].get(
            "content",
            "",
        )
        for chunk in chunks
        if chunk.get("choices")
    )

    assert reconstructed == "partial"

    assert not any(
        (
            chunk.get("choices")
            and chunk["choices"][0].get(
                "finish_reason"
            ) is not None
        )
        for chunk in chunks
    )


def test_legacy_chat_stream_contract_is_unchanged(
    client,
):
    response = client.post(
        "/chat/stream",
        json={
            "provider": "mock",
            "model": "legacy-model",
            "messages": [
                {
                    "role": "user",
                    "content": "legacy",
                }
            ],
            "max_tokens": 16,
        },
    )

    assert response.status_code == 200

    body = response.text

    assert "event: meta" in body
    assert "event: token" in body
    assert "event: usage" in body
    assert "event: done" in body
    assert "chat.completion.chunk" not in body
