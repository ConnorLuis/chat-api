from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from src.app.api import routes_chat as routes_module
from src.app.db.base import Base
from src.app.db.session import (
    build_engine,
    build_session_factory,
)
from src.app.llm.providers import (
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
)
from src.app.main import app
from src.app.services import (
    ConversationService,
    NewMessage,
)


class CapturingProvider:
    name = "mock"

    def __init__(
        self,
        *,
        answer: str = "captured answer",
        fail: bool = False,
    ) -> None:
        self.answer = answer
        self.fail = fail
        self.requests: list[
            ProviderChatRequest
        ] = []

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return requested_model or "capture-model"

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        self.requests.append(request)

        if self.fail:
            raise RuntimeError(
                "forced provider failure"
            )

        return ProviderChatResponse(
            content=self.answer,
            provider=self.name,
            model=(
                request.model
                or "capture-model"
            ),
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        raise AssertionError(
            "stream() is not used by sync /chat"
        )
        yield


@pytest.fixture
def history_environment(
    tmp_path,
    monkeypatch,
):
    database_path = (
        tmp_path
        / "chat_history_test.db"
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


def test_stateless_chat_does_not_use_database(
    monkeypatch,
):
    def fail_session_factory():
        raise AssertionError(
            "stateless chat accessed database"
        )

    monkeypatch.setattr(
        routes_module,
        "get_session_factory",
        fail_session_factory,
    )

    response = TestClient(app).post(
        "/chat",
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
    assert response.json()[
        "conversation_id"
    ] is None


def test_sync_chat_loads_history_and_persists_exchange(
    history_environment,
    monkeypatch,
):
    session_factory = history_environment
    conversation_id = create_conversation(
        session_factory
    )

    with session_factory() as session:
        service = ConversationService(
            session
        )

        service.append_messages(
            conversation_id,
            messages=[
                NewMessage(
                    role="user",
                    content="old question",
                ),
                NewMessage(
                    role="assistant",
                    content="old answer",
                    provider="mock",
                    model="old-model",
                ),
            ],
        )

    provider = CapturingProvider(
        answer="new answer"
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = TestClient(app).post(
        "/chat",
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

    data = response.json()

    assert data["conversation_id"] == (
        conversation_id
    )
    assert data["answer"] == "new answer"

    provider_messages = (
        provider.requests[0].messages
    )

    assert [
        (message.role, message.content)
        for message in provider_messages
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


def test_missing_conversation_returns_404_before_provider(
    history_environment,
    monkeypatch,
):
    provider = CapturingProvider()

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = TestClient(app).post(
        "/chat",
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


def test_provider_failure_does_not_persist_messages(
    history_environment,
    monkeypatch,
):
    session_factory = history_environment
    conversation_id = create_conversation(
        session_factory
    )

    provider = CapturingProvider(
        fail=True
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = TestClient(app).post(
        "/chat",
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

    assert response.status_code == 502

    stored = list_messages(
        session_factory,
        conversation_id,
    )

    assert stored == []


def test_sync_chat_respects_max_turns(
    history_environment,
    monkeypatch,
):
    session_factory = history_environment
    conversation_id = create_conversation(
        session_factory
    )

    with session_factory() as session:
        service = ConversationService(
            session
        )

        service.append_messages(
            conversation_id,
            messages=[
                NewMessage(
                    role="user",
                    content="u1",
                ),
                NewMessage(
                    role="assistant",
                    content="a1",
                ),
                NewMessage(
                    role="user",
                    content="u2",
                ),
                NewMessage(
                    role="assistant",
                    content="a2",
                ),
                NewMessage(
                    role="user",
                    content="u3",
                ),
                NewMessage(
                    role="assistant",
                    content="a3",
                ),
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

    provider = CapturingProvider()

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = TestClient(app).post(
        "/chat",
        json={
            "provider": "mock",
            "conversation_id": conversation_id,
            "messages": [
                {
                    "role": "user",
                    "content": "u4",
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
        ("user", "u3"),
        ("assistant", "a3"),
        ("user", "u4"),
    ]


def test_prompt_system_is_not_persisted(
    history_environment,
    monkeypatch,
):
    session_factory = history_environment
    conversation_id = create_conversation(
        session_factory
    )

    provider = CapturingProvider(
        answer="prompt answer"
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda provider_name: provider,
    )

    response = TestClient(app).post(
        "/chat",
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

    provider_messages = (
        provider.requests[0].messages
    )

    assert provider_messages[0].role == "system"

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
