from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.app.db.base import Base
from src.app.db.types import UTCDateTime
from src.app.db.utils import new_uuid, utc_now


class UsageRecord(Base):
    """一次模型调用的请求级 token accounting 记录."""

    __tablename__ = "usage_records"

    __table_args__ = (
        CheckConstraint(
            (
                "status IN ("
                "'succeeded', "
                "'provider_failed', "
                "'client_disconnected', "
                "'persistence_failed'"
                ")"
            ),
            name="ck_usage_records_status",
        ),
        CheckConstraint(
            (
                "usage_source IN ("
                "'provider_native', "
                "'local_estimate', "
                "'unavailable'"
                ")"
            ),
            name="ck_usage_records_source",
        ),
        CheckConstraint(
            (
                "prompt_tokens IS NULL "
                "OR prompt_tokens >= 0"
            ),
            name="ck_usage_records_prompt_tokens",
        ),
        CheckConstraint(
            (
                "completion_tokens IS NULL "
                "OR completion_tokens >= 0"
            ),
            name="ck_usage_records_completion_tokens",
        ),
        CheckConstraint(
            (
                "total_tokens IS NULL "
                "OR total_tokens >= 0"
            ),
            name="ck_usage_records_total_tokens",
        ),
        CheckConstraint(
            "latency_ms >= 0",
            name="ck_usage_records_latency_ms",
        ),
        CheckConstraint(
            (
                "("
                "usage_source = 'unavailable' "
                "AND prompt_tokens IS NULL "
                "AND completion_tokens IS NULL "
                "AND total_tokens IS NULL"
                ") OR ("
                "usage_source != 'unavailable' "
                "AND prompt_tokens IS NOT NULL "
                "AND completion_tokens IS NOT NULL "
                "AND total_tokens IS NOT NULL"
                ")"
            ),
            name="ck_usage_records_source_tokens",
        ),
        CheckConstraint(
            (
                "total_tokens IS NULL "
                "OR prompt_tokens IS NULL "
                "OR completion_tokens IS NULL "
                "OR total_tokens = "
                "prompt_tokens + completion_tokens"
            ),
            name="ck_usage_records_total_consistency",
        ),
        Index(
            "ix_usage_records_trace_created",
            "trace_id",
            "created_at",
        ),
        Index(
            "ix_usage_records_conversation_created",
            "conversation_id",
            "created_at",
        ),
        Index(
            "ix_usage_records_provider_model_created",
            "provider",
            "model",
            "created_at",
        ),
    )

    request_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    trace_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # 不设置 FK：会话删除后 accounting 记录仍然保留。
    conversation_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    request_kind: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    usage_source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    prompt_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    completion_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    total_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    error_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )
