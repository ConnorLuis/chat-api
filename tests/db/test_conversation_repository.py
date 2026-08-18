from sqlalchemy.orm import Session

from src.app.db.repositories import (
    ConversationRepository,
)


def test_create_get_and_list_conversations(
    db_session: Session,
):
    repository = ConversationRepository(
        db_session
    )

    first = repository.create(
        title="First",
    )
    second = repository.create(
        title="Second",
    )

    db_session.commit()

    loaded = repository.get(
        first.id
    )

    assert loaded is not None
    assert loaded.title == "First"

    conversations = (
        repository.list_conversations(
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


def test_update_conversation_title(
    db_session: Session,
):
    repository = ConversationRepository(
        db_session
    )

    conversation = repository.create(
        title="Old",
    )
    db_session.commit()

    updated = repository.update_title(
        conversation.id,
        title="New",
    )
    db_session.commit()

    assert updated is not None
    assert updated.title == "New"

    loaded = repository.get(
        conversation.id
    )

    assert loaded is not None
    assert loaded.title == "New"


def test_delete_conversation(
    db_session: Session,
):
    repository = ConversationRepository(
        db_session
    )

    conversation = repository.create()
    db_session.commit()

    assert repository.delete(
        conversation.id
    )
    db_session.commit()

    assert repository.get(
        conversation.id
    ) is None

    assert not repository.delete(
        "missing-conversation"
    )
