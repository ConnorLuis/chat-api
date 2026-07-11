from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.requests import Request

from src.app.api import (
    routes_chat as routes_module,
)
from src.app.db.models import (
    Message,
    UsageRecord,
)
from src.app.llm.providers import (
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderUsage,
)
from src.app.llm.schemas import ChatRequest
from src.app.main import app
from src.app.services import (
    ConversationService,
)


def parse_sse_events(
    body: str,
) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []

    normalized = body.replace(
        "\r\n",
        "\n",
    )

    for block in normalized.split(
        "\n\n"
    ):
        block = block.strip("\n")

        if not block.strip():
            continue

        event_name = None
        data_lines: list[str] = []

        for line in block.split("\n"):
            if line.startswith("event:"):
                value = line[len("event:"):]

                if value.startswith(" "):
                    value = value[1:]

                event_name = value

            elif line.startswith("data:"):
                value = line[len("data:"):]

                if value.startswith(" "):
                    value = value[1:]

                data_lines.append(value)

        if event_name is not None:
            events.append(
                (
                    event_name,
                    "\n".join(data_lines),
                )
            )

    return events


class AccountingStreamingProvider:
    name = "mock"

    def __init__(
        self,
        *,
        chunks: tuple[str, ...] = (
            "stream answer",
        ),
        usage: ProviderUsage | None = None,
        fail_after: int | None = None,
    ) -> None:
        self.chunks = chunks
        self.usage = usage
        self.fail_after = fail_after
        self.requests: list[
            ProviderChatRequest
        ] = []

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return (
            requested_model
            or "stream-usage-model"
        )

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        raise AssertionError(
            "chat() is not used by stream tests"
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        self.requests.append(request)

        for index, content in enumerate(
            self.chunks
        ):
            if self.fail_after == index:
                raise RuntimeError(
                    "forced stream failure"
                )

            yield ProviderChatChunk(
                delta=content,
                provider=self.name,
                model=self.resolve_model(
                    request.model
                ),
            )

        if self.fail_after == len(
            self.chunks
        ):
            raise RuntimeError(
                "forced stream failure"
            )

        # Terminal chunk。usage 可以为空，
        # 用于测试 local_estimate 成功路径。
        yield ProviderChatChunk(
            delta="",
            provider=self.name,
            model=self.resolve_model(
                request.model
            ),
            usage=self.usage,
            finish_reason="stop",
        )


class DisconnectStreamingProvider:
    name = "mock"

    def __init__(self) -> None:
        self.closed = False

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return (
            requested_model
            or "disconnect-model"
        )

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        raise AssertionError(
            "chat() is not used"
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        try:
            yield ProviderChatChunk(
                delta="partial",
                provider=self.name,
                model=self.resolve_model(
                    request.model
                ),
            )

            await asyncio.Event().wait()

        finally:
            self.closed = True


def create_conversation(
    session_factory,
) -> str:
    with session_factory() as session:
        conversation = (
            ConversationService(session)
            .create_conversation(
                title="stream accounting",
            )
        )

        return conversation.id


def list_usage_records(
    session_factory,
) -> list[UsageRecord]:
    with session_factory() as session:
        return list(
            session.scalars(
                select(UsageRecord)
                .order_by(
                    UsageRecord
                    .created_at
                    .asc(),
                    UsageRecord
                    .request_id
                    .asc(),
                )
            ).all()
        )


def list_messages(
    session_factory,
    conversation_id: str,
) -> list[Message]:
    with session_factory() as session:
        return list(
            session.scalars(
                select(Message)
                .where(
                    Message.conversation_id
                    == conversation_id
                )
                .order_by(
                    Message.sequence_no.asc()
                )
            ).all()
        )


def test_stream_native_usage_success(
    isolated_stream_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_stream_accounting_db
    )
    conversation_id = create_conversation(
        session_factory
    )

    provider = AccountingStreamingProvider(
        chunks=(
            "native",
            " answer",
        ),
        usage=ProviderUsage(
            prompt_tokens=12,
            completion_tokens=5,
            total_tokens=17,
        ),
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )
    monkeypatch.setattr(
        routes_module,
        "get_trace_id",
        lambda _: "stream-native-trace",
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "model": "native-stream-model",
            "conversation_id": (
                conversation_id
            ),
            "messages": [
                {
                    "role": "user",
                    "content": "native stream",
                }
            ],
        },
    )

    assert response.status_code == 200

    events = parse_sse_events(
        response.text
    )
    event_names = [
        name
        for name, _ in events
    ]

    assert event_names[-2:] == [
        "usage",
        "done",
    ]

    usage = next(
        json.loads(data)
        for name, data in events
        if name == "usage"
    )

    assert usage["status"] == "succeeded"
    assert usage["usage_source"] == (
        "provider_native"
    )
    assert usage["prompt_tokens"] == 12
    assert usage["completion_tokens"] == 5
    assert usage["total_tokens"] == 17
    assert usage["request_id"]

    records = list_usage_records(
        session_factory
    )

    assert len(records) == 1
    record = records[0]

    assert record.request_id == (
        usage["request_id"]
    )
    assert record.trace_id == (
        "stream-native-trace"
    )
    assert record.conversation_id == (
        conversation_id
    )
    assert record.request_kind == (
        "chat_stream"
    )
    assert record.provider == "mock"
    assert record.model == (
        "native-stream-model"
    )
    assert record.status == "succeeded"
    assert record.usage_source == (
        "provider_native"
    )
    assert record.total_tokens == 17
    assert record.latency_ms >= 0

    messages = list_messages(
        session_factory,
        conversation_id,
    )

    assert [
        message.role
        for message in messages
    ] == [
        "user",
        "assistant",
    ]

    # Message 只接收原生 completion token。
    assert messages[-1].token_count == 5


def test_stream_local_estimate_success(
    isolated_stream_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_stream_accounting_db
    )
    conversation_id = create_conversation(
        session_factory
    )

    provider = AccountingStreamingProvider(
        chunks=(
            "estimated",
            " answer",
        ),
        usage=None,
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "conversation_id": (
                conversation_id
            ),
            "messages": [
                {
                    "role": "user",
                    "content": "estimate stream",
                }
            ],
        },
    )

    assert response.status_code == 200

    events = parse_sse_events(
        response.text
    )

    usage = next(
        json.loads(data)
        for name, data in events
        if name == "usage"
    )

    assert usage["status"] == "succeeded"
    assert usage["usage_source"] == (
        "local_estimate"
    )
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == (
        usage["prompt_tokens"]
        + usage["completion_tokens"]
    )

    records = list_usage_records(
        session_factory
    )

    assert len(records) == 1
    assert records[0].status == "succeeded"
    assert records[0].usage_source == (
        "local_estimate"
    )

    messages = list_messages(
        session_factory,
        conversation_id,
    )

    assert len(messages) == 2

    # 本地估算不能伪装成消息级原生 token。
    assert messages[-1].token_count is None


def test_stream_partial_provider_failure_records_estimate(
    isolated_stream_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_stream_accounting_db
    )
    conversation_id = create_conversation(
        session_factory
    )

    provider = AccountingStreamingProvider(
        chunks=("partial",),
        fail_after=1,
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )
    monkeypatch.setattr(
        routes_module,
        "get_trace_id",
        lambda _: "stream-failure-trace",
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "conversation_id": (
                conversation_id
            ),
            "messages": [
                {
                    "role": "user",
                    "content": "partial failure",
                }
            ],
        },
    )

    events = parse_sse_events(
        response.text
    )
    event_names = [
        name
        for name, _ in events
    ]

    assert event_names == [
        "meta",
        "token",
        "error",
    ]
    assert "usage" not in event_names
    assert "done" not in event_names

    error = json.loads(
        events[-1][1]
    )
    usage = error["usage"]

    assert usage["status"] == (
        "provider_failed"
    )
    assert usage["usage_source"] == (
        "local_estimate"
    )
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == (
        usage["prompt_tokens"]
        + usage["completion_tokens"]
    )
    assert usage["request_id"]

    records = list_usage_records(
        session_factory
    )

    assert len(records) == 1
    record = records[0]

    assert record.trace_id == (
        "stream-failure-trace"
    )
    assert record.status == (
        "provider_failed"
    )
    assert record.usage_source == (
        "local_estimate"
    )
    assert record.error_type == (
        "runtimeerror"
    )

    # Provider 失败不保存部分消息。
    assert list_messages(
        session_factory,
        conversation_id,
    ) == []


def test_stream_failure_before_output_is_unavailable(
    isolated_stream_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_stream_accounting_db
    )
    conversation_id = create_conversation(
        session_factory
    )

    provider = AccountingStreamingProvider(
        chunks=("never emitted",),
        fail_after=0,
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "conversation_id": (
                conversation_id
            ),
            "messages": [
                {
                    "role": "user",
                    "content": "fail immediately",
                }
            ],
        },
    )

    events = parse_sse_events(
        response.text
    )

    assert [
        name
        for name, _ in events
    ] == [
        "meta",
        "error",
    ]

    error = json.loads(
        events[-1][1]
    )
    usage = error["usage"]

    assert usage["status"] == (
        "provider_failed"
    )
    assert usage["usage_source"] == (
        "unavailable"
    )
    assert usage["prompt_tokens"] is None
    assert usage[
        "completion_tokens"
    ] is None
    assert usage["total_tokens"] is None

    records = list_usage_records(
        session_factory
    )

    assert len(records) == 1
    assert records[0].usage_source == (
        "unavailable"
    )
    assert records[0].total_tokens is None

    assert list_messages(
        session_factory,
        conversation_id,
    ) == []


def test_stream_client_disconnect_records_partial_usage(
    isolated_stream_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_stream_accounting_db
    )
    conversation_id = create_conversation(
        session_factory
    )

    provider = DisconnectStreamingProvider()

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )
    monkeypatch.setattr(
        routes_module,
        "get_trace_id",
        lambda _: "stream-disconnect-trace",
    )

    async def run_disconnect():
        scope = {
            "type": "http",
            "asgi": {
                "version": "3.0",
            },
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/chat/stream",
            "raw_path": b"/chat/stream",
            "query_string": b"",
            "headers": [],
            "client": (
                "testclient",
                50000,
            ),
            "server": (
                "testserver",
                80,
            ),
        }

        request = Request(scope)

        response = await (
            routes_module.chat_stream(
                request,
                ChatRequest(
                    provider="mock",
                    model="disconnect-model",
                    conversation_id=(
                        conversation_id
                    ),
                    messages=[
                        {
                            "role": "user",
                            "content": "disconnect",
                        }
                    ],
                ),
            )
        )

        iterator = response.body_iterator

        meta_chunk = await anext(iterator)
        token_chunk = await anext(iterator)

        assert "event: meta" in str(
            meta_chunk
        )
        assert "event: token" in str(
            token_chunk
        )

        # 模拟客户端在收到部分输出后断开。
        await iterator.aclose()

    asyncio.run(
        run_disconnect()
    )

    assert provider.closed is True

    records = list_usage_records(
        session_factory
    )

    assert len(records) == 1
    record = records[0]

    assert record.trace_id == (
        "stream-disconnect-trace"
    )
    assert record.conversation_id == (
        conversation_id
    )
    assert record.request_kind == (
        "chat_stream"
    )
    assert record.status == (
        "client_disconnected"
    )
    assert record.usage_source == (
        "local_estimate"
    )
    assert record.prompt_tokens is not None
    assert (
        record.completion_tokens
        is not None
    )
    assert record.completion_tokens > 0
    assert record.total_tokens == (
        record.prompt_tokens
        + record.completion_tokens
    )
    assert record.error_type == (
        "client_disconnect"
    )

    # 断开时只记录请求 accounting，
    # 不保存 user 或部分 assistant。
    assert list_messages(
        session_factory,
        conversation_id,
    ) == []


def test_stream_persistence_failure_records_consumed_usage(
    isolated_stream_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_stream_accounting_db
    )
    conversation_id = create_conversation(
        session_factory
    )

    provider = AccountingStreamingProvider(
        chunks=("generated answer",),
        usage=None,
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )

    def fail_atomic_persistence(
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "forced stream persistence failure"
        )

    monkeypatch.setattr(
        routes_module,
        "persist_sync_exchange_and_usage",
        fail_atomic_persistence,
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "conversation_id": (
                conversation_id
            ),
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "generate but fail storage"
                    ),
                }
            ],
        },
    )

    events = parse_sse_events(
        response.text
    )
    event_names = [
        name
        for name, _ in events
    ]

    assert event_names == [
        "meta",
        "token",
        "error",
    ]
    assert "usage" not in event_names
    assert "done" not in event_names

    error = json.loads(
        events[-1][1]
    )
    usage = error["usage"]

    assert usage["status"] == (
        "persistence_failed"
    )
    assert usage["usage_source"] == (
        "local_estimate"
    )
    assert usage["request_id"]
    assert usage["total_tokens"] == (
        usage["prompt_tokens"]
        + usage["completion_tokens"]
    )

    records = list_usage_records(
        session_factory
    )

    assert len(records) == 1
    record = records[0]

    assert record.status == (
        "persistence_failed"
    )
    assert record.usage_source == (
        "local_estimate"
    )
    assert record.error_type == (
        "runtimeerror"
    )

    assert list_messages(
        session_factory,
        conversation_id,
    ) == []
