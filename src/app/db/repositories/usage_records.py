from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from src.app.db.models import UsageRecord


class UsageRecordRepository:
    """UsageRecord query/flush 边界，不负责 commit."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def create(
        self,
        *,
        trace_id: str,
        conversation_id: str | None,
        caller_key_id: str | None = None,
        request_kind: str,
        provider: str,
        model: str,
        status: str,
        usage_source: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
        latency_ms: int,
        error_type: str | None = None,
    ) -> UsageRecord:
        record = UsageRecord(
            trace_id=trace_id,
            conversation_id=conversation_id,
            caller_key_id=caller_key_id,
            request_kind=request_kind,
            provider=provider,
            model=model,
            status=status,
            usage_source=usage_source,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            error_type=error_type,
        )

        self.session.add(record)
        self.session.flush()

        return record

    def get(
        self,
        request_id: str,
    ) -> UsageRecord | None:
        return self.session.get(
            UsageRecord,
            request_id,
        )

    def list_by_trace(
        self,
        trace_id: str,
    ) -> list[UsageRecord]:
        statement = (
            select(UsageRecord)
            .where(
                UsageRecord.trace_id
                == trace_id
            )
            .order_by(
                UsageRecord.created_at.asc(),
                UsageRecord.request_id.asc(),
            )
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )



    def sum_total_tokens_for_caller(
        self,
        *,
        caller_key_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Sum known consumed tokens for one UTC range.

        SQL SUM ignores NULL total_tokens, so usage_unavailable
        records remain visible accounting facts but do not
        fabricate token consumption.
        """

        statement = (
            select(
                func.coalesce(
                    func.sum(
                        UsageRecord.total_tokens
                    ),
                    0,
                )
            )
            .where(
                UsageRecord.caller_key_id
                == caller_key_id,
                UsageRecord.created_at
                >= start_time,
                UsageRecord.created_at
                < end_time,
            )
        )

        return int(
            self.session.scalar(
                statement
            )
            or 0
        )
