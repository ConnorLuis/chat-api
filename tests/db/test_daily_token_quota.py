from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import inspect

from src.app.db.models import (
    UsageRecord,
)
from src.app.db.repositories import (
    UsageRecordRepository,
)
from src.app.limits import (
    DailyTokenQuotaService,
)


DAY_START = datetime(
    2026,
    7,
    11,
    tzinfo=timezone.utc,
)


class FixedClock:
    def __init__(
        self,
        value: datetime,
    ) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


def add_usage(
    session,
    *,
    caller_key_id: str | None,
    total_tokens: int | None,
    created_at: datetime,
    status: str = "succeeded",
):
    if total_tokens is None:
        usage_source = "unavailable"
        prompt_tokens = None
        completion_tokens = None

    else:
        usage_source = "local_estimate"
        prompt_tokens = total_tokens
        completion_tokens = 0

    record = UsageRecord(
        trace_id=(
            f"trace-{caller_key_id}-"
            f"{created_at.timestamp()}"
        ),
        conversation_id=None,
        caller_key_id=caller_key_id,
        request_kind="chat_sync",
        provider="mock",
        model="quota-model",
        status=status,
        usage_source=usage_source,
        prompt_tokens=prompt_tokens,
        completion_tokens=(
            completion_tokens
        ),
        total_tokens=total_tokens,
        latency_ms=1,
        error_type=None,
        created_at=created_at,
    )

    session.add(record)
    session.flush()

    return record


def test_usage_record_has_caller_column_and_index(
    db_engine,
):
    inspector = inspect(db_engine)

    columns = {
        item["name"]
        for item in inspector.get_columns(
            "usage_records"
        )
    }
    indexes = {
        item["name"]
        for item in inspector.get_indexes(
            "usage_records"
        )
    }

    assert "caller_key_id" in columns
    assert (
        "ix_usage_records_caller_created"
        in indexes
    )


def test_repository_returns_zero_without_usage(
    db_session,
):
    repository = UsageRecordRepository(
        db_session
    )

    assert (
        repository
        .sum_total_tokens_for_caller(
            caller_key_id="key-1",
            start_time=DAY_START,
            end_time=(
                DAY_START
                + timedelta(days=1)
            ),
        )
        == 0
    )


def test_repository_filters_caller_and_utc_range(
    db_session,
):
    add_usage(
        db_session,
        caller_key_id="key-1",
        total_tokens=40,
        created_at=(
            DAY_START
            + timedelta(hours=1)
        ),
    )
    add_usage(
        db_session,
        caller_key_id="key-1",
        total_tokens=25,
        created_at=(
            DAY_START
            + timedelta(hours=2)
        ),
        status="provider_failed",
    )
    add_usage(
        db_session,
        caller_key_id="key-2",
        total_tokens=500,
        created_at=(
            DAY_START
            + timedelta(hours=3)
        ),
    )
    add_usage(
        db_session,
        caller_key_id="key-1",
        total_tokens=1000,
        created_at=(
            DAY_START
            - timedelta(seconds=1)
        ),
    )

    repository = UsageRecordRepository(
        db_session
    )

    assert (
        repository
        .sum_total_tokens_for_caller(
            caller_key_id="key-1",
            start_time=DAY_START,
            end_time=(
                DAY_START
                + timedelta(days=1)
            ),
        )
        == 65
    )


def test_unknown_usage_does_not_add_tokens(
    db_session,
):
    add_usage(
        db_session,
        caller_key_id="key-1",
        total_tokens=None,
        created_at=(
            DAY_START
            + timedelta(hours=1)
        ),
        status="provider_failed",
    )

    repository = UsageRecordRepository(
        db_session
    )

    assert (
        repository
        .sum_total_tokens_for_caller(
            caller_key_id="key-1",
            start_time=DAY_START,
            end_time=(
                DAY_START
                + timedelta(days=1)
            ),
        )
        == 0
    )


def test_quota_allows_below_limit(
    db_session,
):
    add_usage(
        db_session,
        caller_key_id="key-1",
        total_tokens=60,
        created_at=(
            DAY_START
            + timedelta(hours=1)
        ),
    )

    service = DailyTokenQuotaService(
        db_session,
        limit=100,
        clock=FixedClock(
            DAY_START
            + timedelta(hours=12)
        ),
    )

    decision = service.check("key-1")

    assert decision.allowed is True
    assert decision.used_tokens == 60
    assert (
        decision.remaining_tokens
        == 40
    )
    assert decision.window_start == (
        DAY_START
    )
    assert decision.reset_at == (
        DAY_START
        + timedelta(days=1)
    )
    assert (
        decision.retry_after_seconds
        == 0
    )


def test_quota_denies_at_limit(
    db_session,
):
    add_usage(
        db_session,
        caller_key_id="key-1",
        total_tokens=100,
        created_at=(
            DAY_START
            + timedelta(hours=1)
        ),
    )

    service = DailyTokenQuotaService(
        db_session,
        limit=100,
        clock=FixedClock(
            DAY_START
            + timedelta(hours=12)
        ),
    )

    decision = service.check("key-1")

    assert decision.allowed is False
    assert decision.used_tokens == 100
    assert (
        decision.remaining_tokens
        == 0
    )
    assert (
        decision.retry_after_seconds
        == 12 * 60 * 60
    )


def test_quota_uses_utc_day_boundary(
    db_session,
):
    add_usage(
        db_session,
        caller_key_id="key-1",
        total_tokens=90,
        created_at=(
            DAY_START
            - timedelta(seconds=1)
        ),
    )
    add_usage(
        db_session,
        caller_key_id="key-1",
        total_tokens=10,
        created_at=DAY_START,
    )

    service = DailyTokenQuotaService(
        db_session,
        limit=50,
        clock=FixedClock(
            DAY_START
            + timedelta(minutes=1)
        ),
    )

    decision = service.check("key-1")

    assert decision.allowed is True
    assert decision.used_tokens == 10
    assert (
        decision.remaining_tokens
        == 40
    )


def test_quota_rejects_invalid_limit(
    db_session,
):
    with pytest.raises(ValueError):
        DailyTokenQuotaService(
            db_session,
            limit=0,
        )
