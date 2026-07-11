import json

import pytest

from src.app.cost import (
    build_pricing_key,
    load_pricing_catalog,
)


def write_catalog(
    tmp_path,
    *,
    prices,
    version="test-v1",
    currency="USD",
):
    path = tmp_path / "pricing.json"
    path.write_text(
        json.dumps({
            "version": version,
            "currency": currency,
            "unit_tokens": 1_000_000,
            "prices": prices,
        }),
        encoding="utf-8",
    )
    return path


def test_exact_rate_precedes_wildcard(
    tmp_path,
):
    path = write_catalog(
        tmp_path,
        prices=[
            {
                "provider": "openai",
                "model": "*",
                "prompt_price_per_unit": "1",
                "completion_price_per_unit": "2",
            },
            {
                "provider": "openai",
                "model": "paid-model",
                "prompt_price_per_unit": "3",
                "completion_price_per_unit": "4",
            },
        ],
    )

    catalog = load_pricing_catalog(
        path
    )

    exact = catalog.lookup(
        "OPENAI",
        "Paid-Model",
    )
    wildcard = catalog.lookup(
        "openai",
        "other-model",
    )

    assert exact is not None
    assert exact.key == (
        "openai:paid-model"
    )
    assert str(
        exact.prompt_price_per_unit
    ) == "3"

    assert wildcard is not None
    assert wildcard.key == "openai:*"


def test_unknown_provider_model_returns_none(
    tmp_path,
):
    catalog = load_pricing_catalog(
        write_catalog(
            tmp_path,
            prices=[],
        )
    )

    assert catalog.lookup(
        "unknown",
        "model",
    ) is None


def test_pricing_key_is_normalized():
    assert build_pricing_key(
        " OpenAI ",
        " GPT-X ",
    ) == "openai:gpt-x"


def test_duplicate_pricing_key_rejected(
    tmp_path,
):
    path = write_catalog(
        tmp_path,
        prices=[
            {
                "provider": "openai",
                "model": "x",
                "prompt_price_per_unit": "1",
                "completion_price_per_unit": "2",
            },
            {
                "provider": "OPENAI",
                "model": "X",
                "prompt_price_per_unit": "3",
                "completion_price_per_unit": "4",
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="duplicate pricing key",
    ):
        load_pricing_catalog(path)


def test_negative_price_rejected(
    tmp_path,
):
    path = write_catalog(
        tmp_path,
        prices=[
            {
                "provider": "openai",
                "model": "x",
                "prompt_price_per_unit": "-1",
                "completion_price_per_unit": "2",
            }
        ],
    )

    with pytest.raises(
        ValueError,
        match="must be >= 0",
    ):
        load_pricing_catalog(path)
