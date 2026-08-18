from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

from .catalog import (
    PricingCatalog,
    build_pricing_key,
)


COST_STATUS_ESTIMATED = "estimated"
COST_STATUS_UNKNOWN_PRICE = (
    "unknown_price"
)
COST_STATUS_USAGE_UNAVAILABLE = (
    "usage_unavailable"
)

COST_QUANTUM = Decimal(
    "0.000000000001"
)


@dataclass(
    frozen=True,
    slots=True,
)
class CostSnapshot:
    pricing_key: str
    matched_pricing_key: str | None
    pricing_version: str
    currency: str
    unit_tokens: int
    cost_status: str
    prompt_price_per_unit: Decimal | None
    completion_price_per_unit: Decimal | None
    prompt_cost: Decimal | None
    completion_cost: Decimal | None
    estimated_cost: Decimal | None


def _quantize_cost(
    value: Decimal,
) -> Decimal:
    return value.quantize(
        COST_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def _calculate_component(
    *,
    tokens: int,
    price_per_unit: Decimal,
    unit_tokens: int,
) -> Decimal:
    return _quantize_cost(
        (
            Decimal(tokens)
            * price_per_unit
        )
        / Decimal(unit_tokens)
    )


def estimate_usage_cost(
    *,
    provider: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    catalog: PricingCatalog,
) -> CostSnapshot:
    pricing_key = build_pricing_key(
        provider,
        model,
    )

    if (
        prompt_tokens is None
        or completion_tokens is None
    ):
        return CostSnapshot(
            pricing_key=pricing_key,
            matched_pricing_key=None,
            pricing_version=(
                catalog.version
            ),
            currency=catalog.currency,
            unit_tokens=(
                catalog.unit_tokens
            ),
            cost_status=(
                COST_STATUS_USAGE_UNAVAILABLE
            ),
            prompt_price_per_unit=None,
            completion_price_per_unit=None,
            prompt_cost=None,
            completion_cost=None,
            estimated_cost=None,
        )

    if (
        prompt_tokens < 0
        or completion_tokens < 0
    ):
        raise ValueError(
            "token values must be >= 0"
        )

    rate = catalog.lookup(
        provider,
        model,
    )

    if rate is None:
        return CostSnapshot(
            pricing_key=pricing_key,
            matched_pricing_key=None,
            pricing_version=(
                catalog.version
            ),
            currency=catalog.currency,
            unit_tokens=(
                catalog.unit_tokens
            ),
            cost_status=(
                COST_STATUS_UNKNOWN_PRICE
            ),
            prompt_price_per_unit=None,
            completion_price_per_unit=None,
            prompt_cost=None,
            completion_cost=None,
            estimated_cost=None,
        )

    prompt_cost = _calculate_component(
        tokens=prompt_tokens,
        price_per_unit=(
            rate.prompt_price_per_unit
        ),
        unit_tokens=catalog.unit_tokens,
    )

    completion_cost = (
        _calculate_component(
            tokens=completion_tokens,
            price_per_unit=(
                rate
                .completion_price_per_unit
            ),
            unit_tokens=(
                catalog.unit_tokens
            ),
        )
    )

    estimated_cost = _quantize_cost(
        prompt_cost
        + completion_cost
    )

    return CostSnapshot(
        pricing_key=pricing_key,
        matched_pricing_key=rate.key,
        pricing_version=catalog.version,
        currency=catalog.currency,
        unit_tokens=catalog.unit_tokens,
        cost_status=(
            COST_STATUS_ESTIMATED
        ),
        prompt_price_per_unit=(
            rate.prompt_price_per_unit
        ),
        completion_price_per_unit=(
            rate.completion_price_per_unit
        ),
        prompt_cost=prompt_cost,
        completion_cost=completion_cost,
        estimated_cost=estimated_cost,
    )
