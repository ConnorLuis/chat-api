from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.app.db.session import SessionFactory
from src.app.services import (
    ConversationService,
    NewMessage,
)

from .context_window import ContextMessage


@dataclass(
    frozen=True,
    slots=True,
)
class ConversationHistorySnapshot:
    conversation_id: str
    messages: tuple[ContextMessage, ...]


def load_conversation_history(
    *,
    session_factory: SessionFactory,
    conversation_id: str,
    limit: int,
) -> ConversationHistorySnapshot:
    """使用短 Session 读取持久化历史并立即释放连接."""

    with session_factory() as session:
        service = ConversationService(session)

        messages = service.list_recent_messages(
            conversation_id,
            limit=limit,
        )

        return ConversationHistorySnapshot(
            conversation_id=conversation_id,
            messages=tuple(
                ContextMessage(
                    role=message.role,
                    content=message.content,
                )
                for message in messages
            ),
        )


def persist_conversation_exchange(
    *,
    session_factory: SessionFactory,
    conversation_id: str,
    request_messages: Sequence[ContextMessage],
    assistant_content: str,
    provider: str,
    model: str,
    assistant_token_count: int | None = None,
) -> None:
    """原子保存本次显式请求消息和最终 assistant 回复."""

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
            token_count=assistant_token_count,
        )
    )

    with session_factory() as session:
        service = ConversationService(session)

        service.append_messages(
            conversation_id,
            messages=new_messages,
        )
