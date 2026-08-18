from decimal import Decimal

from sqlalchemy.orm import Session

from src.app.cost import (
    PricingCatalog,
    PricingRate,
)
from src.app.services import (
    ConversationService,
    NewUsageRecord,
    UsageCostService,
    UsageService,
)


def catalog():
    rate = PricingRate(
        provider="openai",
        model="paid-model",
        prompt_price_per_unit=(
            Decimal("2.5")
        ),
        completion_price_per_unit=(
            Decimal("10")
        ),
    )

    return PricingCatalog(
        version="test-v1",
        currency="USD",
        unit_tokens=1_000_000,
        rates={
            rate.key: rate,
        },
    )


def create_usage(
    db_session: Session,
    *,
    provider="openai",
    model="paid-model",
    prompt_tokens=1000,
    completion_tokens=500,
    status="succeeded",
    usage_source="provider_native",
    conversation_id=None,
):
    total_tokens = (
        prompt_tokens + completion_tokens
        if (
            prompt_tokens is not None
            and completion_tokens is not None
        )
        else None
    )

    return UsageService(
        db_session
    ).record_usage(
        NewUsageRecord(
            trace_id="cost-service-trace",
            conversation_id=conversation_id,
            request_kind="chat_sync",
            provider=provider,
            model=model,
            status=status,
            usage_source=usage_source,
            prompt_tokens=prompt_tokens,
            completion_tokens=(
                completion_tokens
            ),
            total_tokens=total_tokens,
            latency_ms=5,
        )
    )


def test_record_estimated_cost(
    db_session: Session,
):
    usage = create_usage(db_session)

    service = UsageCostService(
        db_session,
        catalog=catalog(),
    )

    cost = service.record_cost_for_usage(
        usage
    )

    assert cost.cost_status == (
        "estimated"
    )
    assert cost.pricing_version == (
        "test-v1"
    )
    assert cost.estimated_cost == (
        Decimal("0.007500000000")
    )


def test_record_unknown_price(
    db_session: Session,
):
    usage = create_usage(
        db_session,
        provider="other",
        model="missing",
    )

    cost = UsageCostService(
        db_session,
        catalog=catalog(),
    ).record_cost_for_usage(usage)

    assert cost.cost_status == (
        "unknown_price"
    )
    assert cost.estimated_cost is None


def test_record_usage_unavailable(
    db_session: Session,
):
    usage = create_usage(
        db_session,
        prompt_tokens=None,
        completion_tokens=None,
        status="provider_failed",
        usage_source="unavailable",
    )

    cost = UsageCostService(
        db_session,
        catalog=catalog(),
    ).record_cost_for_usage(usage)

    assert cost.cost_status == (
        "usage_unavailable"
    )
    assert cost.estimated_cost is None


def test_cost_survives_conversation_delete(
    db_session: Session,
):
    conversation = ConversationService(
        db_session
    ).create_conversation(
        title="cost retention",
    )

    usage = create_usage(
        db_session,
        conversation_id=conversation.id,
    )

    cost = UsageCostService(
        db_session,
        catalog=catalog(),
    ).record_cost_for_usage(usage)

    assert ConversationService(
        db_session
    ).delete_conversation(
        conversation.id
    ) is True

    loaded = UsageCostService(
        db_session,
        catalog=catalog(),
    ).get_cost(cost.request_id)

    assert loaded is not None
    assert loaded.estimated_cost == (
        Decimal("0.007500000000")
    )
