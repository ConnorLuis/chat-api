from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from src.app.core.settings import settings


def normalize_provider(value: str) -> str:
    normalized = value.strip().casefold()

    if not normalized:
        raise ValueError(
            "pricing provider must not be empty"
        )

    return normalized


def normalize_model(value: str | None) -> str:
    normalized = (
        value.strip().casefold()
        if value is not None
        else ""
    )

    return normalized or "unknown"


def build_pricing_key(
    provider: str,
    model: str | None,
) -> str:
    return (
        f"{normalize_provider(provider)}:"
        f"{normalize_model(model)}"
    )


def _parse_non_negative_decimal(
    value,
    *,
    field_name: str,
) -> Decimal:
    try:
        parsed = Decimal(str(value))

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be a decimal"
        ) from exc

    if not parsed.is_finite():
        raise ValueError(
            f"{field_name} must be finite"
        )

    if parsed < 0:
        raise ValueError(
            f"{field_name} must be >= 0"
        )

    return parsed


@dataclass(
    frozen=True,
    slots=True,
)
class PricingRate:
    provider: str
    model: str
    prompt_price_per_unit: Decimal
    completion_price_per_unit: Decimal

    @property
    def key(self) -> str:
        return build_pricing_key(
            self.provider,
            self.model,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class PricingCatalog:
    version: str
    currency: str
    unit_tokens: int
    rates: Mapping[str, PricingRate]

    def lookup(
        self,
        provider: str,
        model: str | None,
    ) -> PricingRate | None:
        exact_key = build_pricing_key(
            provider,
            model,
        )

        exact = self.rates.get(exact_key)

        if exact is not None:
            return exact

        wildcard_key = build_pricing_key(
            provider,
            "*",
        )

        return self.rates.get(
            wildcard_key
        )


def load_pricing_catalog(
    path: str | Path,
) -> PricingCatalog:
    catalog_path = Path(path)

    try:
        payload = json.loads(
            catalog_path.read_text(
                encoding="utf-8"
            )
        )

    except FileNotFoundError as exc:
        raise ValueError(
            "Pricing catalog does not exist: "
            f"{catalog_path}"
        ) from exc

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Pricing catalog is not valid JSON: "
            f"{catalog_path}"
        ) from exc

    version = str(
        payload.get("version", "")
    ).strip()

    if not version:
        raise ValueError(
            "pricing catalog version "
            "must not be empty"
        )

    currency = str(
        payload.get("currency", "")
    ).strip().upper()

    if (
        len(currency) != 3
        or not currency.isalpha()
    ):
        raise ValueError(
            "pricing catalog currency must "
            "be a 3-letter code"
        )

    try:
        unit_tokens = int(
            payload.get("unit_tokens")
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "pricing catalog unit_tokens "
            "must be an integer"
        ) from exc

    if unit_tokens <= 0:
        raise ValueError(
            "pricing catalog unit_tokens "
            "must be greater than 0"
        )

    raw_prices = payload.get(
        "prices"
    )

    if not isinstance(
        raw_prices,
        list,
    ):
        raise ValueError(
            "pricing catalog prices "
            "must be a list"
        )

    rates: dict[
        str,
        PricingRate,
    ] = {}

    for index, raw in enumerate(
        raw_prices
    ):
        if not isinstance(raw, dict):
            raise ValueError(
                "pricing entry must be "
                f"an object: index={index}"
            )

        provider = normalize_provider(
            str(raw.get("provider", ""))
        )
        model = normalize_model(
            str(raw.get("model", ""))
        )

        rate = PricingRate(
            provider=provider,
            model=model,
            prompt_price_per_unit=(
                _parse_non_negative_decimal(
                    raw.get(
                        "prompt_price_per_unit"
                    ),
                    field_name=(
                        "prompt_price_per_unit"
                    ),
                )
            ),
            completion_price_per_unit=(
                _parse_non_negative_decimal(
                    raw.get(
                        "completion_price_per_unit"
                    ),
                    field_name=(
                        "completion_price_per_unit"
                    ),
                )
            ),
        )

        if rate.key in rates:
            raise ValueError(
                "duplicate pricing key: "
                f"{rate.key}"
            )

        rates[rate.key] = rate

    return PricingCatalog(
        version=version,
        currency=currency,
        unit_tokens=unit_tokens,
        rates=MappingProxyType(rates),
    )


@lru_cache(maxsize=8)
def _load_cached_catalog(
    path: str,
) -> PricingCatalog:
    return load_pricing_catalog(path)


def get_pricing_catalog(
    path: str | None = None,
) -> PricingCatalog:
    selected = (
        path
        or settings.PRICING_CATALOG_PATH
    )

    return _load_cached_catalog(
        str(Path(selected))
    )


def clear_pricing_catalog_cache() -> None:
    _load_cached_catalog.cache_clear()
