import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.db.models import Message
from src.app.services import (
    ConversationNotFoundError,
    ConversationService,
    InvalidMessageRoleError,
)


def test_service_create_rename_and_list(
    conversation_service: ConversationService,
):
    first = (
        conversation_service
        .create_conversation(
            title="  First  ",
        )
    )

    second = (
        conversation_service
        .create_conversation()
    )

    assert first.title == "First"
    assert second.title is None

    renamed = (
        conversation_service
        .rename_conversation(
            first.id,
            title="Renamed",
        )
    )

    assert renamed.title == "Renamed"

    conversations = (
        conversation_service
        .list_conversations(
            limit=10,
            offset=0,
        )
    )

    assert {
        conversation.id
        for conversation in conversations
    } == {
        first.id,
        second.id,
    }


def test_service_add_get_list_and_delete_message(
    conversation_service: ConversationService,
):
    conversation = (
        conversation_service
        .create_conversation(
            title="Chat",
        )
    )

    user_message = (
        conversation_service.add_message(
            conversation.id,
            role="USER",
            content="hello",
        )
    )

    assistant_message = (
        conversation_service.add_message(
            conversation.id,
            role="assistant",
            content="world",
            provider=" MOCK ",
            model="mock-model",
            token_count=4,
        )
    )

    assert user_message.role == "user"
    assert assistant_message.provider == "mock"
    assert assistant_message.token_count == 4

    loaded = conversation_service.get_message(
        assistant_message.id
    )

    assert loaded is not None
    assert loaded.content == "world"

    messages = (
        conversation_service.list_messages(
            conversation.id
        )
    )

    assert [
        message.id
        for message in messages
    ] == [
        user_message.id,
        assistant_message.id,
    ]

    assert conversation_service.delete_message(
        user_message.id
    )

    remaining = (
        conversation_service.list_messages(
            conversation.id
        )
    )

    assert [
        message.id
        for message in remaining
    ] == [
        assistant_message.id,
    ]


def test_delete_conversation_cascades_messages(
    conversation_service: ConversationService,
    db_session: Session,
):
    conversation = (
        conversation_service
        .create_conversation()
    )

    conversation_service.add_message(
        conversation.id,
        role="user",
        content="one",
    )

    conversation_service.add_message(
        conversation.id,
        role="assistant",
        content="two",
    )

    before = db_session.scalar(
        select(
            func.count(Message.id)
        )
    )

    assert before == 2

    assert (
        conversation_service
        .delete_conversation(
            conversation.id
        )
    )

    after = db_session.scalar(
        select(
            func.count(Message.id)
        )
    )

    assert after == 0


def test_service_rejects_invalid_message_input(
    conversation_service: ConversationService,
):
    conversation = (
        conversation_service
        .create_conversation()
    )

    with pytest.raises(
        InvalidMessageRoleError
    ):
        conversation_service.add_message(
            conversation.id,
            role="tool",
            content="invalid",
        )

    with pytest.raises(
        ValueError,
        match="content must not be empty",
    ):
        conversation_service.add_message(
            conversation.id,
            role="user",
            content="   ",
        )

    with pytest.raises(
        ValueError,
        match="token_count",
    ):
        conversation_service.add_message(
            conversation.id,
            role="assistant",
            content="answer",
            token_count=-1,
        )

    with pytest.raises(
        ConversationNotFoundError
    ):
        conversation_service.add_message(
            "missing-conversation",
            role="user",
            content="hello",
        )


def test_service_rolls_back_when_commit_fails(
    conversation_service: ConversationService,
    db_session: Session,
    monkeypatch,
):
    conversation = (
        conversation_service
        .create_conversation()
    )

    def fail_commit() -> None:
        raise RuntimeError(
            "forced commit failure"
        )

    monkeypatch.setattr(
        db_session,
        "commit",
        fail_commit,
    )

    with pytest.raises(
        RuntimeError,
        match="forced commit failure",
    ):
        conversation_service.add_message(
            conversation.id,
            role="user",
            content="must rollback",
        )

    message_count = db_session.scalar(
        select(
            func.count(Message.id)
        )
    )

    assert message_count == 0
