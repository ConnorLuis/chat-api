import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.app.db.repositories import (
    ConversationRepository,
    MessageRepository,
)


def test_create_get_and_list_messages(
    db_session: Session,
):
    conversations = ConversationRepository(
        db_session
    )
    messages = MessageRepository(
        db_session
    )

    conversation = conversations.create(
        title="Messages",
    )
    db_session.commit()

    first = messages.create(
        conversation_id=conversation.id,
        role="user",
        content="hello",
    )

    second = messages.create(
        conversation_id=conversation.id,
        role="assistant",
        content="world",
        provider="mock",
        model="mock-model",
        token_count=3,
    )

    db_session.commit()

    loaded = messages.get(
        second.id
    )

    assert loaded is not None
    assert loaded.provider == "mock"
    assert loaded.model == "mock-model"
    assert loaded.token_count == 3

    listed = messages.list_by_conversation(
        conversation.id
    )

    assert [
        message.id
        for message in listed
    ] == [
        first.id,
        second.id,
    ]

    assert [
        message.sequence_no
        for message in listed
    ] == [1, 2]


def test_delete_message(
    db_session: Session,
):
    conversations = ConversationRepository(
        db_session
    )
    messages = MessageRepository(
        db_session
    )

    conversation = conversations.create()
    message = messages.create(
        conversation_id=conversation.id,
        role="user",
        content="delete me",
    )

    db_session.commit()

    assert messages.delete(
        message.id
    )
    db_session.commit()

    assert messages.get(
        message.id
    ) is None

    assert not messages.delete(
        "missing-message"
    )


def test_message_requires_existing_conversation(
    db_session: Session,
):
    messages = MessageRepository(
        db_session
    )

    with pytest.raises(
        IntegrityError
    ):
        messages.create(
            conversation_id=(
                "missing-conversation"
            ),
            role="user",
            content="orphan",
        )

    db_session.rollback()
