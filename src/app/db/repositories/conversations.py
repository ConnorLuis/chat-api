from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app.db.models import Conversation
from src.app.db.utils import new_uuid


class ConversationRepository:
    """Conversation 的纯持久化操作，不负责事务提交."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def create(
        self,
        *,
        title: str | None = None,
        conversation_id: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            id=conversation_id or new_uuid(),
            title=title,
        )

        self.session.add(
            conversation
        )
        self.session.flush()

        return conversation

    def get(
        self,
        conversation_id: str,
    ) -> Conversation | None:
        return self.session.get(
            Conversation,
            conversation_id,
        )

    def list_conversations(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        statement = (
            select(Conversation)
            .order_by(
                Conversation.updated_at.desc(),
                Conversation.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def update_title(
        self,
        conversation_id: str,
        *,
        title: str | None,
    ) -> Conversation | None:
        conversation = self.get(
            conversation_id
        )

        if conversation is None:
            return None

        conversation.title = title
        self.session.flush()

        return conversation

    def delete(
        self,
        conversation_id: str,
    ) -> bool:
        conversation = self.get(
            conversation_id
        )

        if conversation is None:
            return False

        self.session.delete(
            conversation
        )
        self.session.flush()

        return True
