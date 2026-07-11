from __future__ import annotations

from collections.abc import Sequence

from src.app.conversations import ContextMessage
from src.app.db.models import UsageRecord
from src.app.db.session import SessionFactory
from src.app.services import (
    ConversationService,
    NewMessage,
    NewUsageRecord,
    UsageService,
)


def persist_usage_only(
    *,
    session_factory: SessionFactory,
    usage: NewUsageRecord,
) -> UsageRecord:
    """独立持久化一次请求级 usage."""

    with session_factory() as session:
        return UsageService(
            session
        ).record_usage(usage)


def persist_sync_exchange_and_usage(
    *,
    session_factory: SessionFactory,
    conversation_id: str | None,
    request_messages: Sequence[ContextMessage],
    assistant_content: str,
    provider: str,
    model: str,
    assistant_token_count: int | None,
    usage: NewUsageRecord,
) -> UsageRecord:
    """原子持久化同步消息交换和请求级 usage.

    conversation_id 为空时只保存 UsageRecord。
    """

    with session_factory() as session:
        if conversation_id is not None:
            new_messages = [
                NewMessage(
                    role=message.role,
                    content=message.content,
                )
                for message in request_messages
            ]

            new_messages.append(
                NewMessage(
                    role="assistant",
                    content=assistant_content,
                    provider=provider,
                    model=model,
                    token_count=(
                        assistant_token_count
                    ),
                )
            )

            ConversationService(
                session
            ).append_messages(
                conversation_id,
                messages=new_messages,
                commit=False,
            )

        record = UsageService(
            session
        ).record_usage(
            usage,
            commit=False,
        )

        try:
            session.commit()
            session.refresh(record)
            return record

        except Exception:
            session.rollback()
            raise
