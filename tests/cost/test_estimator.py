from decimal import Decimal

from src.app.cost import (
    COST_STATUS_ESTIMATED,
    COST_STATUS_UNKNOWN_PRICE,
    COST_STATUS_USAGE_UNAVAILABLE,
    PricingCatalog,
    PricingRate,
    estimate_usage_cost,
)


def paid_catalog():
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

    zero = PricingRate(
        provider="mock",
        model="*",
        prompt_price_per_unit=(
            Decimal("0")
        ),
        completion_price_per_unit=(
            Decimal("0")
        ),
    )

    return PricingCatalog(
        version="test-v1",
        currency="USD",
        unit_tokens=1_000_000,
        rates={
            rate.key: rate,
            zero.key: zero,
        },
    )


def test_estimated_cost_uses_separate_rates():
    snapshot = estimate_usage_cost(
        provider="openai",
        model="paid-model",
        prompt_tokens=1000,
        completion_tokens=500,
        catalog=paid_catalog(),
    )

    assert snapshot.cost_status == (
        COST_STATUS_ESTIMATED
    )
    assert snapshot.prompt_cost == (
        Decimal("0.002500000000")
    )
    assert snapshot.completion_cost == (
        Decimal("0.005000000000")
    )
    assert snapshot.estimated_cost == (
        Decimal("0.007500000000")
    )


def test_explicit_zero_price_is_estimated():
    snapshot = estimate_usage_cost(
        provider="mock",
        model="anything",
        prompt_tokens=10,
        completion_tokens=20,
        catalog=paid_catalog(),
    )

    assert snapshot.cost_status == (
        COST_STATUS_ESTIMATED
    )
    assert snapshot.matched_pricing_key == (
        "mock:*"
    )
    assert snapshot.estimated_cost == (
        Decimal("0.000000000000")
    )


def test_unknown_price_is_not_zero():
    snapshot = estimate_usage_cost(
        provider="other",
        model="unknown",
        prompt_tokens=10,
        completion_tokens=20,
        catalog=paid_catalog(),
    )

    assert snapshot.cost_status == (
        COST_STATUS_UNKNOWN_PRICE
    )
    assert snapshot.estimated_cost is None
    assert (
        snapshot.matched_pricing_key
        is None
    )


def test_unavailable_usage_has_no_cost():
    snapshot = estimate_usage_cost(
        provider="openai",
        model="paid-model",
        prompt_tokens=None,
        completion_tokens=None,
        catalog=paid_catalog(),
    )

    assert snapshot.cost_status == (
        COST_STATUS_USAGE_UNAVAILABLE
    )
    assert snapshot.estimated_cost is None
