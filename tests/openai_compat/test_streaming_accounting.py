from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy import select

from src.app.api.openai_compat import (
    routes_chat_completions as routes_module,
)
from src.app.api.openai_compat.streaming import (
    _stream_events,
)
from src.app.db.models import (
    UsageCost,
    UsageRecord,
)
from src.app.llm.providers import (
    ChatProviderError,
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderMessage,
    ProviderUsage,
)
from src.app.services import NewUsageRecord
from src.app.usage.persistence import (
    persist_usage_only,
)


REQUEST_KIND = (
    "openai_chat_completions_stream"
)


class SuccessfulStreamingProvider:
    name = "fake-stream"

    def __init__(self) -> None:
        self.calls = 0

    def resolve_model(
        self,
        requested_model=None,
    ):
        return (
            requested_model
            or "fake-stream-model"
        )

    def chat(self, request):
        raise AssertionError

    async def stream(
        self,
        request,
    ) -> AsyncIterator[
        ProviderChatChunk
    ]:
        self.calls += 1

        yield ProviderChatChunk(
            delta="hello",
            provider=self.name,
            model="actual-stream-model",
        )
        yield ProviderChatChunk(
            delta=" world",
            provider=self.name,
            model="actual-stream-model",
        )
        yield ProviderChatChunk(
            delta="",
            provider=self.name,
            model="actual-stream-model",
            finish_reason="stop",
            usage=ProviderUsage(
                prompt_tokens=8,
                completion_tokens=2,
                total_tokens=10,
            ),
        )


class PartialFailureProvider:
    name = "partial-failure"

    def resolve_model(
        self,
        requested_model=None,
    ):
        return (
            requested_model
            or "partial-model"
        )

    def chat(self, request):
        raise AssertionError

    async def stream(
        self,
        request,
    ) -> AsyncIterator[
        ProviderChatChunk
    ]:
        yield ProviderChatChunk(
            delta="partial output",
            provider=self.name,
            model="partial-model",
        )

        raise ChatProviderError(
            "stream exploded"
        )


def auth_headers(context):
    return {
        "Authorization": (
            f"Bearer {context['api_key']}"
        )
    }


def stream_payload():
    return {
        "provider": "mock",
        "model": "requested-stream-model",
        "messages": [
            {
                "role": "user",
                "content": "stream accounting",
            }
        ],
        "stream": True,
        "stream_options": {
            "include_usage": True,
        },
    }


def load_stream_records(context):
    with context[
        "session_factory"
    ]() as session:
        return list(
            session.scalars(
                select(UsageRecord)
                .where(
                    UsageRecord.request_kind
                    == REQUEST_KIND
                )
                .order_by(
                    UsageRecord
                    .created_at
                    .asc()
                )
            ).all()
        )


def test_stream_success_persists_usage_and_cost(
    auth_context,
    monkeypatch,
):
    provider = (
        SuccessfulStreamingProvider()
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _name: provider,
    )

    response = auth_context[
        "client"
    ].post(
        "/v1/chat/completions",
        headers=auth_headers(
            auth_context
        ),
        json=stream_payload(),
    )

    assert response.status_code == 200
    assert "data: [DONE]" in response.text
    assert provider.calls == 1

    records = load_stream_records(
        auth_context
    )

    assert len(records) == 1

    record = records[0]

    assert record.status == "succeeded"
    assert (
        record.caller_key_id
        == auth_context["key_id"]
    )
    assert (
        record.usage_source
        == "provider_native"
    )
    assert record.total_tokens == 10

    with auth_context[
        "session_factory"
    ]() as session:
        cost = session.get(
            UsageCost,
            record.request_id,
        )

    assert cost is not None


def test_partial_failure_persists_consumed_usage(
    auth_context,
    monkeypatch,
):
    provider = PartialFailureProvider()

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _name: provider,
    )

    response = auth_context[
        "client"
    ].post(
        "/v1/chat/completions",
        headers=auth_headers(
            auth_context
        ),
        json=stream_payload(),
    )

    assert response.status_code == 200
    assert "provider_error" in response.text
    assert "data: [DONE]" not in response.text

    records = load_stream_records(
        auth_context
    )

    assert len(records) == 1

    record = records[0]

    assert (
        record.status
        == "provider_failed"
    )
    assert (
        record.usage_source
        == "local_estimate"
    )
    assert record.total_tokens is not None
    assert record.total_tokens > 0


def test_stream_close_records_client_disconnected(
    auth_context,
):
    provider = (
        SuccessfulStreamingProvider()
    )

    provider_request = (
        ProviderChatRequest(
            messages=[
                ProviderMessage(
                    role="user",
                    content="disconnect",
                )
            ],
            model="disconnect-model",
            temperature=1.0,
            top_p=1.0,
            max_tokens=32,
        )
    )

    trace_id = (
        f"disconnect-{uuid4()}"
    )

    async def close_early():
        generator = _stream_events(
            provider=provider,
            request=provider_request,
            requested_model=(
                "disconnect-model"
            ),
            include_usage=False,
            session_factory=(
                auth_context[
                    "session_factory"
                ]
            ),
            trace_id=trace_id,
            caller_key_id=(
                auth_context["key_id"]
            ),
        )

        # role chunk
        await anext(generator)

        # first content chunk
        await anext(generator)

        await generator.aclose()

    asyncio.run(close_early())

    with auth_context[
        "session_factory"
    ]() as session:
        record = session.scalar(
            select(UsageRecord)
            .where(
                UsageRecord.trace_id
                == trace_id
            )
        )

    assert record is not None
    assert (
        record.status
        == "client_disconnected"
    )
    assert (
        record.caller_key_id
        == auth_context["key_id"]
    )
    assert (
        record.usage_source
        == "local_estimate"
    )
    assert record.total_tokens is not None


def test_openai_stream_quota_returns_429(
    auth_context,
    monkeypatch,
):
    monkeypatch.setenv(
        "TOKEN_QUOTA_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "DAILY_TOKEN_QUOTA_TOKENS",
        "10",
    )

    persist_usage_only(
        session_factory=(
            auth_context[
                "session_factory"
            ]
        ),
        usage=NewUsageRecord(
            trace_id=(
                f"quota-{uuid4()}"
            ),
            conversation_id=None,
            caller_key_id=(
                auth_context["key_id"]
            ),
            request_kind="quota_seed",
            provider="mock",
            model="quota-model",
            status="succeeded",
            usage_source="local_estimate",
            prompt_tokens=10,
            completion_tokens=0,
            total_tokens=10,
            latency_ms=1,
        ),
    )

    calls = []

    def provider_factory(name):
        calls.append(name)
        return SuccessfulStreamingProvider()

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        provider_factory,
    )

    response = auth_context[
        "client"
    ].post(
        "/v1/chat/completions",
        headers=auth_headers(
            auth_context
        ),
        json=stream_payload(),
    )

    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "message": (
                "Daily token quota exceeded"
            ),
            "type": "rate_limit_error",
            "param": None,
            "code": (
                "daily_token_quota_exceeded"
            ),
        }
    }

    assert calls == []

    assert response.headers[
        "x-tokenquota-limit"
    ] == "10"
    assert response.headers[
        "x-tokenquota-used"
    ] == "10"
    assert response.headers[
        "x-tokenquota-remaining"
    ] == "0"


def test_allowed_openai_stream_has_quota_headers(
    auth_context,
    monkeypatch,
):
    monkeypatch.setenv(
        "TOKEN_QUOTA_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "DAILY_TOKEN_QUOTA_TOKENS",
        "1000",
    )

    provider = (
        SuccessfulStreamingProvider()
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _name: provider,
    )

    response = auth_context[
        "client"
    ].post(
        "/v1/chat/completions",
        headers=auth_headers(
            auth_context
        ),
        json=stream_payload(),
    )

    assert response.status_code == 200
    assert response.headers[
        "x-tokenquota-limit"
    ] == "1000"
    assert response.headers[
        "x-tokenquota-used"
    ] == "0"
    assert response.headers[
        "x-tokenquota-remaining"
    ] == "1000"
