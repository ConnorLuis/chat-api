from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from math import ceil

from sqlalchemy.orm import Session

from src.app.db.repositories import (
    UsageRecordRepository,
)

from .clock import (
    Clock,
    SystemClock,
)
from .models import (
    DailyTokenQuotaDecision,
)


def utc_day_bounds(
    now: datetime,
) -> tuple[datetime, datetime]:
    if (
        now.tzinfo is None
        or now.utcoffset() is None
    ):
        raise ValueError(
            "now must be timezone-aware"
        )

    utc_now = now.astimezone(
        timezone.utc
    )

    start = utc_now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return (
        start,
        start + timedelta(days=1),
    )


class DailyTokenQuotaService:
    """Database-fact daily token quota.

    当前为 soft quota：
    admission 基于已经持久化的 usage facts。
    一个已放行的并发请求可能使最终消耗略微越过限额。
    """

    def __init__(
        self,
        session: Session,
        *,
        limit: int,
        clock: Clock | None = None,
    ) -> None:
        if limit < 1:
            raise ValueError(
                "daily token quota limit "
                "must be greater than or "
                "equal to 1"
            )

        self.session = session
        self.limit = limit
        self.clock = (
            clock
            or SystemClock()
        )
        self.records = (
            UsageRecordRepository(session)
        )

    def check(
        self,
        caller_key_id: str,
    ) -> DailyTokenQuotaDecision:
        normalized = (
            caller_key_id.strip()
        )

        if not normalized:
            raise ValueError(
                "caller_key_id must not "
                "be empty"
            )

        now = self.clock.now()
        start, end = utc_day_bounds(now)

        used_tokens = (
            self.records
            .sum_total_tokens_for_caller(
                caller_key_id=normalized,
                start_time=start,
                end_time=end,
            )
        )

        allowed = (
            used_tokens < self.limit
        )

        remaining = max(
            0,
            self.limit - used_tokens,
        )

        retry_after = (
            0
            if allowed
            else max(
                1,
                ceil(
                    (
                        end
                        - now.astimezone(
                            timezone.utc
                        )
                    ).total_seconds()
                ),
            )
        )

        return DailyTokenQuotaDecision(
            caller_key_id=normalized,
            allowed=allowed,
            limit=self.limit,
            used_tokens=used_tokens,
            remaining_tokens=remaining,
            window_start=start,
            reset_at=end,
            retry_after_seconds=(
                retry_after
            ),
        )
