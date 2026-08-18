from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from src.app.db.base import Base
from src.app.db.types import UTCDateTime
from src.app.db.utils import new_uuid, utc_now

if TYPE_CHECKING:
    from .conversation import Conversation


class Message(Base):
    """Conversation 内的一条纯文本消息."""

    __tablename__ = "messages"

    __table_args__ = (
        CheckConstraint(
            (
                "role IN "
                "('developer', 'system', 'user', 'assistant')"
            ),
            name="ck_messages_role",
        ),
        CheckConstraint(
            (
                "token_count IS NULL "
                "OR token_count >= 0"
            ),
            name="ck_messages_token_count",
        ),
        CheckConstraint(
            "sequence_no >= 1",
            name="ck_messages_sequence_no",
        ),
        UniqueConstraint(
            "conversation_id",
            "sequence_no",
            name=(
                "uq_messages_conversation_sequence"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    sequence_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    model: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )

    conversation: Mapped["Conversation"] = relationship(
        back_populates="messages",
    )
