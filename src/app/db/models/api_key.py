from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Index,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.app.db.base import Base
from src.app.db.types import UTCDateTime
from src.app.db.utils import utc_now


API_KEY_STATUS_ACTIVE = "active"
API_KEY_STATUS_REVOKED = "revoked"


class APIKey(Base):
    """不可恢复的 API key credential metadata."""

    __tablename__ = "api_keys"

    __table_args__ = (
        CheckConstraint(
            (
                "status IN ("
                "'active', "
                "'revoked'"
                ")"
            ),
            name="ck_api_keys_status",
        ),
        CheckConstraint(
            (
                "("
                "status = 'active' "
                "AND revoked_at IS NULL"
                ") OR ("
                "status = 'revoked' "
                "AND revoked_at IS NOT NULL"
                ")"
            ),
            name=(
                "ck_api_keys_revocation_state"
            ),
        ),
        Index(
            "ux_api_keys_prefix",
            "prefix",
            unique=True,
        ),
        Index(
            "ux_api_keys_hash",
            "key_hash",
            unique=True,
        ),
        Index(
            "ix_api_keys_status_created",
            "status",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 可公开展示和用于数据库精确查找。
    prefix: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    # HMAC-SHA256 hex digest，固定 64 字符。
    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=API_KEY_STATUS_ACTIVE,
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            UTCDateTime(),
            nullable=False,
            default=utc_now,
        )
    )

    revoked_at: Mapped[
        datetime | None
    ] = mapped_column(
        UTCDateTime(),
        nullable=True,
    )
