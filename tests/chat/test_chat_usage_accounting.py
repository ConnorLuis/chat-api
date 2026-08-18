from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.app.api import routes_chat as routes_module
from src.app.db.base import Base
from src.app.db.models import (
    Message,
    UsageRecord,
)
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
from src.app.main import app
from src.app.services import ConversationService


class UsageProvider:
    name = "mock"

    def __init__(
        self,
        *,
        usage: ProviderUsage | None = None,
        fail: bool = False,
    ) -> None:
        self.usage = usage
        self.fail = fail

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return requested_model or "usage-model"

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        if self.fail:
            raise RuntimeError(
                "forced usage provider failure"
            )

        return ProviderChatResponse(
            content="usage answer",
            provider=self.name,
            model=self.resolve_model(
                request.model
            ),
            usage=self.usage,
            finish_reason="stop",
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        raise AssertionError(
            "stream is not used"
        )
        yield


@pytest.fixture
def usage_chat_environment(
    tmp_path,
    monkeypatch,
):
    engine = build_engine(
        "sqlite:///"
        f"{tmp_path / 'chat_usage.db'}"
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
        return (
            ConversationService(session)
            .create_conversation()
            .id
        )


def usage_records(
    session_factory,
) -> list[UsageRecord]:
    with session_factory() as session:
        return list(
            session.scalars(
                select(UsageRecord)
                .order_by(
                    UsageRecord
                    .created_at
                    .asc()
                )
            ).all()
        )


def test_sync_native_usage_is_persisted_and_exposed(
    usage_chat_environment,
    monkeypatch,
):
    session_factory = usage_chat_environment
    conversation_id = create_conversation(
        session_factory
    )

    provider = UsageProvider(
        usage=ProviderUsage(
            prompt_tokens=10,
            completion_tokens=4,
            total_tokens=14,
        )
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )

    response = TestClient(app).post(
        "/chat",
        json={
            "provider": "mock",
            "model": "native-model",
            "conversation_id": (
                conversation_id
            ),
            "messages": [
                {
                    "role": "user",
                    "content": "native usage",
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    usage = data["metadata"]["usage"]

    assert usage["usage_source"] == (
        "provider_native"
    )
    assert usage["prompt_tokens"] == 10
    assert usage["completion_tokens"] == 4
    assert usage["total_tokens"] == 14

    records = usage_records(
        session_factory
    )

    assert len(records) == 1
    record = records[0]

    assert record.request_id == (
        usage["request_id"]
    )
    assert record.trace_id == (
        data["trace_id"]
    )
    assert record.conversation_id == (
        conversation_id
    )
    assert record.request_kind == (
        "chat_sync"
    )
    assert record.provider == "mock"
    assert record.model == "native-model"
    assert record.status == "succeeded"
    assert record.usage_source == (
        "provider_native"
    )
    assert record.total_tokens == 14
    assert record.latency_ms >= 0

    with session_factory() as session:
        messages = list(
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

    assert len(messages) == 2
    assert messages[-1].token_count == 4


def test_sync_provider_failure_records_unavailable_usage(
    usage_chat_environment,
    monkeypatch,
):
    session_factory = usage_chat_environment
    conversation_id = create_conversation(
        session_factory
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: UsageProvider(
            fail=True
        ),
    )

    response = TestClient(app).post(
        "/chat",
        json={
            "provider": "mock",
            "conversation_id": (
                conversation_id
            ),
            "messages": [
                {
                    "role": "user",
                    "content": "fail",
                }
            ],
        },
    )

    assert response.status_code == 502

    records = usage_records(
        session_factory
    )

    assert len(records) == 1
    record = records[0]

    assert record.status == (
        "provider_failed"
    )
    assert record.usage_source == (
        "unavailable"
    )
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert record.total_tokens is None
    assert record.error_type == (
        "runtimeerror"
    )

    with session_factory() as session:
        messages = list(
            session.scalars(
                select(Message).where(
                    Message.conversation_id
                    == conversation_id
                )
            ).all()
        )

    assert messages == []


def test_sync_persistence_failure_records_consumed_usage(
    usage_chat_environment,
    monkeypatch,
):
    session_factory = usage_chat_environment
    conversation_id = create_conversation(
        session_factory
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: UsageProvider(),
    )

    def fail_append(
        self,
        conversation_id,
        *,
        messages,
        commit=True,
    ):
        raise RuntimeError(
            "forced persistence failure"
        )

    monkeypatch.setattr(
        ConversationService,
        "append_messages",
        fail_append,
    )

    response = TestClient(app).post(
        "/chat",
        json={
            "provider": "mock",
            "conversation_id": (
                conversation_id
            ),
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "generated but not stored"
                    ),
                }
            ],
        },
    )

    assert response.status_code == 500

    records = usage_records(
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
    assert record.prompt_tokens is not None
    assert (
        record.completion_tokens
        is not None
    )
    assert record.total_tokens == (
        record.prompt_tokens
        + record.completion_tokens
    )
    assert record.error_type == (
        "runtimeerror"
    )

    with session_factory() as session:
        messages = list(
            session.scalars(
                select(Message).where(
                    Message.conversation_id
                    == conversation_id
                )
            ).all()
        )

    assert messages == []
