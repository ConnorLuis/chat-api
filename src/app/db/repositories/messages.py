from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.db.models import Message
from src.app.db.utils import new_uuid


class MessageRepository:
    """Message 的纯持久化操作，不负责事务提交."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def next_sequence_no(
        self,
        conversation_id: str,
    ) -> int:
        statement = (
            select(
                func.coalesce(
                    func.max(
                        Message.sequence_no
                    ),
                    0,
                )
            )
            .where(
                Message.conversation_id
                == conversation_id
            )
        )

        current = self.session.scalar(
            statement
        )

        return int(current or 0) + 1

    def create(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        token_count: int | None = None,
        sequence_no: int | None = None,
        message_id: str | None = None,
    ) -> Message:
        resolved_sequence = (
            sequence_no
            if sequence_no is not None
            else self.next_sequence_no(
                conversation_id
            )
        )

        message = Message(
            id=message_id or new_uuid(),
            conversation_id=conversation_id,
            sequence_no=resolved_sequence,
            role=role,
            content=content,
            provider=provider,
            model=model,
            token_count=token_count,
        )

        self.session.add(message)
        self.session.flush()

        return message

    def get(
        self,
        message_id: str,
    ) -> Message | None:
        return self.session.get(
            Message,
            message_id,
        )

    def list_by_conversation(
        self,
        conversation_id: str,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Message]:
        statement = (
            select(Message)
            .where(
                Message.conversation_id
                == conversation_id
            )
            .order_by(
                Message.sequence_no.asc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def list_recent_by_conversation(
        self,
        conversation_id: str,
        *,
        limit: int,
    ) -> list[Message]:
        """返回最近的消息，并恢复为正序."""

        statement = (
            select(Message)
            .where(
                Message.conversation_id
                == conversation_id
            )
            .order_by(
                Message.sequence_no.desc(),
            )
            .limit(limit)
        )

        messages = list(
            self.session.scalars(
                statement
            ).all()
        )

        messages.reverse()

        return messages

    def delete(
        self,
        message_id: str,
    ) -> bool:
        message = self.get(message_id)

        if message is None:
            return False

        self.session.delete(message)
        self.session.flush()

        return True
