from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from src.app.api import (
    routes_chat as routes_module,
)
from src.app.db.base import Base
from src.app.db.session import (
    build_engine,
    build_session_factory,
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
    NewMessage,
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


class StreamingProvider:
    name = "mock"

    def __init__(
        self,
        *,
        chunks: tuple[str, ...] = (
            "stream answer",
        ),
        fail_after: int | None = None,
    ) -> None:
        self.chunks = chunks
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
            or "stream-model"
        )

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        raise AssertionError(
            "chat() is not used by /chat/stream"
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
                model=(
                    request.model
                    or "stream-model"
                ),
            )

        if self.fail_after == len(
            self.chunks
        ):
            raise RuntimeError(
                "forced stream failure"
            )

        yield ProviderChatChunk(
            delta="",
            provider=self.name,
            model=(
                request.model
                or "stream-model"
            ),
            usage=ProviderUsage(
                prompt_tokens=8,
                completion_tokens=3,
                total_tokens=11,
            ),
            finish_reason="stop",
        )


class BlockingProvider:
    name = "mock"

    def __init__(self) -> None:
        self.requests: list[
            ProviderChatRequest
        ] = []
        self.closed = False

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return (
            requested_model
            or "blocking-model"
        )

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        raise AssertionError

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        self.requests.append(request)

        try:
            yield ProviderChatChunk(
                delta="partial",
                provider=self.name,
                model=(
                    request.model
                    or "blocking-model"
                ),
            )

            await asyncio.Event().wait()

        finally:
            self.closed = True


@pytest.fixture
def stream_history_environment(
    tmp_path,
    monkeypatch,
):
    database_path = (
        tmp_path
        / "stream_history_test.db"
    )

    engine = build_engine(
        f"sqlite:///{database_path}"
    )

    Base.metadata.create_all(engine)

    session_factory = (
        build_session_factory(engine)
    )

    monkeypatch.setattr(
        routes_module,
        "get_session_factory",
        lambda: session_factory,
    )

    monkeypatch.setenv(
        "RUN_LOG_PATH",
        str(tmp_path / "runs.jsonl"),
    )

    try:
        yield session_factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_conversation(
    session_factory,
) -> str:
    with session_factory() as session:
        conversation = (
            ConversationService(session)
            .create_conversation()
        )

        return conversation.id


def list_messages(
    session_factory,
    conversation_id: str,
):
    with session_factory() as session:
        return (
            ConversationService(session)
            .list_messages(
                conversation_id
            )
        )


def test_stateless_stream_does_not_use_database(
    monkeypatch,
):
    def fail_session_factory():
        raise AssertionError(
            "stateless stream accessed database"
        )

    monkeypatch.setattr(
        routes_module,
        "get_session_factory",
        fail_session_factory,
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "messages": [
                {
                    "role": "user",
                    "content": "stateless",
                }
            ],
        },
    )

    assert response.status_code == 200

    events = parse_sse_events(
        response.text
    )

    meta = json.loads(events[0][1])

    assert meta["conversation_id"] is None
    assert meta["context_window"] is None


def test_stream_loads_history_and_persists_before_done(
    stream_history_environment,
    monkeypatch,
):
    session_factory = (
        stream_history_environment
    )
    conversation_id = create_conversation(
        session_factory
    )

    with session_factory() as session:
        ConversationService(
            session
        ).append_messages(
            conversation_id,
            messages=[
                NewMessage(
                    role="user",
                    content="old question",
                ),
                NewMessage(
                    role="assistant",
                    content="old answer",
                ),
            ],
        )

    provider = StreamingProvider(
        chunks=(
            "new",
            " answer",
        )
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    operation_order: list[str] = []

    original_persist = (
        routes_module
        .persist_conversation_exchange
    )
    original_sse_event = (
        routes_module.sse_event
    )

    def tracked_persist(
        *args,
        **kwargs,
    ):
        operation_order.append(
            "persist"
        )

        return original_persist(
            *args,
            **kwargs,
        )

    def tracked_sse_event(
        event_type,
        data,
    ):
        operation_order.append(
            event_type
        )

        return original_sse_event(
            event_type,
            data,
        )

    monkeypatch.setattr(
        routes_module,
        "persist_conversation_exchange",
        tracked_persist,
    )
    monkeypatch.setattr(
        routes_module,
        "sse_event",
        tracked_sse_event,
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "model": "new-model",
            "conversation_id": conversation_id,
            "messages": [
                {
                    "role": "user",
                    "content": "new question",
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

    assert event_names[0] == "meta"
    assert event_names[-2:] == [
        "usage",
        "done",
    ]

    meta = json.loads(events[0][1])

    assert meta["conversation_id"] == (
        conversation_id
    )
    assert meta["context_window"][
        "history_messages"
    ] == 2

    usage = next(
        json.loads(data)
        for name, data in events
        if name == "usage"
    )

    assert usage["conversation_id"] == (
        conversation_id
    )

    assert [
        (message.role, message.content)
        for message
        in provider.requests[0].messages
    ] == [
        ("user", "old question"),
        ("assistant", "old answer"),
        ("user", "new question"),
    ]

    stored = list_messages(
        session_factory,
        conversation_id,
    )

    assert [
        message.sequence_no
        for message in stored
    ] == [1, 2, 3, 4]

    assert [
        (message.role, message.content)
        for message in stored
    ] == [
        ("user", "old question"),
        ("assistant", "old answer"),
        ("user", "new question"),
        ("assistant", "new answer"),
    ]

    assert stored[-1].provider == "mock"
    assert stored[-1].model == "new-model"
    assert stored[-1].token_count == 3

    assert (
        operation_order.index("persist")
        < operation_order.index("usage")
        < operation_order.index("done")
    )


def test_missing_conversation_returns_404_before_sse(
    stream_history_environment,
    monkeypatch,
):
    provider = StreamingProvider()

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "conversation_id": (
                "00000000-0000-0000-0000-000000000000"
            ),
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
        },
    )

    assert response.status_code == 404
    assert provider.requests == []


def test_stream_provider_failure_does_not_persist(
    stream_history_environment,
    monkeypatch,
):
    session_factory = (
        stream_history_environment
    )
    conversation_id = create_conversation(
        session_factory
    )

    provider = StreamingProvider(
        chunks=("partial",),
        fail_after=1,
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "conversation_id": conversation_id,
            "messages": [
                {
                    "role": "user",
                    "content": "must not persist",
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

    error = json.loads(
        events[-1][1]
    )

    assert error["conversation_id"] == (
        conversation_id
    )

    assert list_messages(
        session_factory,
        conversation_id,
    ) == []


def test_stream_respects_max_turns(
    stream_history_environment,
    monkeypatch,
):
    session_factory = (
        stream_history_environment
    )
    conversation_id = create_conversation(
        session_factory
    )

    with session_factory() as session:
        ConversationService(
            session
        ).append_messages(
            conversation_id,
            messages=[
                NewMessage("user", "u1"),
                NewMessage("assistant", "a1"),
                NewMessage("user", "u2"),
                NewMessage("assistant", "a2"),
            ],
        )

    monkeypatch.setenv(
        "CONVERSATION_HISTORY_MAX_TURNS",
        "1",
    )
    monkeypatch.setenv(
        "CONVERSATION_CONTEXT_TOKEN_BUDGET",
        "1000",
    )

    provider = StreamingProvider()

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "conversation_id": conversation_id,
            "messages": [
                {
                    "role": "user",
                    "content": "u3",
                }
            ],
        },
    )

    assert response.status_code == 200

    assert [
        (message.role, message.content)
        for message
        in provider.requests[0].messages
    ] == [
        ("user", "u2"),
        ("assistant", "a2"),
        ("user", "u3"),
    ]


def test_stream_prompt_system_is_not_persisted(
    stream_history_environment,
    monkeypatch,
):
    session_factory = (
        stream_history_environment
    )
    conversation_id = create_conversation(
        session_factory
    )

    provider = StreamingProvider(
        chunks=("prompt answer",)
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "conversation_id": conversation_id,
            "prompt_id": "chat",
            "prompt_version": "v1",
            "prompt_vars": {},
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
        },
    )

    assert response.status_code == 200

    assert (
        provider.requests[0]
        .messages[0]
        .role
        == "system"
    )

    stored = list_messages(
        session_factory,
        conversation_id,
    )

    assert [
        message.role
        for message in stored
    ] == [
        "user",
        "assistant",
    ]


def test_client_disconnect_does_not_persist_partial_answer(
    stream_history_environment,
    monkeypatch,
):
    session_factory = (
        stream_history_environment
    )
    conversation_id = create_conversation(
        session_factory
    )

    provider = BlockingProvider()

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )
    monkeypatch.setattr(
        routes_module,
        "get_trace_id",
        lambda request: "disconnect-trace",
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

        iterator = (
            response.body_iterator
        )

        meta_chunk = await anext(
            iterator
        )
        token_chunk = await anext(
            iterator
        )

        assert "event: meta" in str(
            meta_chunk
        )
        assert "event: token" in str(
            token_chunk
        )

        await iterator.aclose()

    asyncio.run(
        run_disconnect()
    )

    assert provider.closed is True

    assert list_messages(
        session_factory,
        conversation_id,
    ) == []
