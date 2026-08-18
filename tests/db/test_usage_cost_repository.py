from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.app.cost import CostSnapshot
from src.app.db.repositories import (
    UsageCostRepository,
)
from src.app.services import (
    NewUsageRecord,
    UsageService,
)


def priced_snapshot():
    return CostSnapshot(
        pricing_key="openai:paid-model",
        matched_pricing_key=(
            "openai:paid-model"
        ),
        pricing_version="test-v1",
        currency="USD",
        unit_tokens=1_000_000,
        cost_status="estimated",
        prompt_price_per_unit=(
            Decimal("2.5")
        ),
        completion_price_per_unit=(
            Decimal("10")
        ),
        prompt_cost=(
            Decimal("0.002500000000")
        ),
        completion_cost=(
            Decimal("0.005000000000")
        ),
        estimated_cost=(
            Decimal("0.007500000000")
        ),
    )


def create_usage(
    db_session: Session,
):
    return UsageService(
        db_session
    ).record_usage(
        NewUsageRecord(
            trace_id="cost-trace",
            conversation_id=None,
            request_kind="chat_sync",
            provider="openai",
            model="paid-model",
            status="succeeded",
            usage_source=(
                "provider_native"
            ),
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            latency_ms=10,
        )
    )


def test_create_and_get_usage_cost(
    db_session: Session,
):
    usage = create_usage(db_session)

    repository = UsageCostRepository(
        db_session
    )

    created = repository.create(
        request_id=usage.request_id,
        snapshot=priced_snapshot(),
    )

    db_session.commit()

    loaded = repository.get(
        usage.request_id
    )

    assert loaded is not None
    assert loaded.request_id == (
        created.request_id
    )
    assert loaded.cost_status == (
        "estimated"
    )
    assert loaded.estimated_cost == (
        Decimal("0.007500000000")
    )


def test_usage_cost_requires_usage_record(
    db_session: Session,
):
    repository = UsageCostRepository(
        db_session
    )

    with pytest.raises(
        IntegrityError,
    ):
        repository.create(
            request_id=(
                "00000000-0000-0000-0000-000000000000"
            ),
            snapshot=priced_snapshot(),
        )

    db_session.rollback()
