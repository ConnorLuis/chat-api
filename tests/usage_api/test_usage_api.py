from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from decimal import Decimal

from fastapi.testclient import TestClient

from src.app.db.models import (
    Message,
    UsageCost,
    UsageRecord,
)
from src.app.main import app


UTC = timezone.utc


def add_usage(
    session,
    *,
    trace_id: str,
    created_at: datetime,
    provider: str,
    model: str,
    status: str,
    usage_source: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    latency_ms: int,
    cost_status: str | None,
):
    total_tokens = (
        prompt_tokens
        + completion_tokens
        if (
            prompt_tokens is not None
            and completion_tokens
            is not None
        )
        else None
    )

    usage = UsageRecord(
        trace_id=trace_id,
        conversation_id=None,
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
        latency_ms=latency_ms,
        created_at=created_at,
    )

    session.add(usage)
    session.flush()

    if cost_status is None:
        return usage

    common = {
        "request_id": usage.request_id,
        "pricing_key": (
            f"{provider}:{model}"
        ),
        "pricing_version": "test-v1",
        "currency": "USD",
        "unit_tokens": 1_000_000,
        "cost_status": cost_status,
        "created_at": created_at,
    }

    if cost_status == "estimated":
        cost = UsageCost(
            **common,
            matched_pricing_key=(
                f"{provider}:*"
            ),
            prompt_price_per_unit=(
                Decimal("0")
            ),
            completion_price_per_unit=(
                Decimal("0")
            ),
            prompt_cost=(
                Decimal("0")
            ),
            completion_cost=(
                Decimal("0")
            ),
            estimated_cost=(
                Decimal("0")
            ),
        )

    else:
        cost = UsageCost(
            **common,
            matched_pricing_key=None,
            prompt_price_per_unit=None,
            completion_price_per_unit=None,
            prompt_cost=None,
            completion_cost=None,
            estimated_cost=None,
        )

    session.add(cost)

    return usage


def seed_usage(
    session_factory,
):
    with session_factory() as session:
        # 2026-07-01: two successful requests.
        add_usage(
            session,
            trace_id="trace-1",
            created_at=datetime(
                2026, 7, 1, 1,
                tzinfo=UTC,
            ),
            provider="mock",
            model="mock-shared",
            status="succeeded",
            usage_source=(
                "provider_native"
            ),
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=10,
            cost_status="estimated",
        )

        add_usage(
            session,
            trace_id="trace-2",
            created_at=datetime(
                2026, 7, 1, 2,
                tzinfo=UTC,
            ),
            provider="openai",
            model="gpt-test",
            status="succeeded",
            usage_source=(
                "provider_native"
            ),
            prompt_tokens=200,
            completion_tokens=100,
            latency_ms=20,
            cost_status="unknown_price",
        )

        # 2026-07-02: unavailable failure
        # and partial disconnect.
        add_usage(
            session,
            trace_id="trace-3",
            created_at=datetime(
                2026, 7, 2, 1,
                tzinfo=UTC,
            ),
            provider="mock",
            model="mock-failed",
            status="provider_failed",
            usage_source="unavailable",
            prompt_tokens=None,
            completion_tokens=None,
            latency_ms=30,
            cost_status=(
                "usage_unavailable"
            ),
        )

        add_usage(
            session,
            trace_id="trace-4",
            created_at=datetime(
                2026, 7, 2, 2,
                tzinfo=UTC,
            ),
            provider="mock",
            model="mock-shared",
            status=(
                "client_disconnected"
            ),
            usage_source=(
                "local_estimate"
            ),
            prompt_tokens=40,
            completion_tokens=10,
            latency_ms=40,
            cost_status="estimated",
        )

        # Historical Day7-style record:
        # token exists but no UsageCost snapshot.
        add_usage(
            session,
            trace_id="trace-5",
            created_at=datetime(
                2026, 7, 3, 1,
                tzinfo=UTC,
            ),
            provider="openai",
            model="gpt-test",
            status=(
                "persistence_failed"
            ),
            usage_source=(
                "local_estimate"
            ),
            prompt_tokens=20,
            completion_tokens=5,
            latency_ms=50,
            cost_status=None,
        )

        session.commit()


def test_pricing_catalog_endpoint(
    isolated_usage_api_db,
):
    response = TestClient(app).get(
        "/usage/pricing"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["version"] == (
        "2026-07-11-v1"
    )
    assert data["currency"] == "USD"
    assert data["unit_tokens"] == (
        1_000_000
    )

    keys = {
        item["pricing_key"]
        for item in data["prices"]
    }

    assert "mock:*" in keys
    assert "ollama:*" in keys


def test_usage_records_pagination_and_filters(
    isolated_usage_api_db,
):
    seed_usage(
        isolated_usage_api_db
    )

    response = TestClient(app).get(
        "/usage/records",
        params={
            "start_time": (
                "2026-07-01T00:00:00Z"
            ),
            "end_time": (
                "2026-07-03T00:00:00Z"
            ),
            "provider": "mock",
            "limit": 2,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["pagination"] == {
        "total": 3,
        "limit": 2,
        "offset": 1,
        "returned": 2,
        "has_more": False,
    }

    assert [
        item["trace_id"]
        for item in data["items"]
    ] == [
        "trace-3",
        "trace-1",
    ]


def test_missing_cost_snapshot_filter(
    isolated_usage_api_db,
):
    seed_usage(
        isolated_usage_api_db
    )

    response = TestClient(app).get(
        "/usage/records",
        params={
            "cost_status": (
                "missing_snapshot"
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["pagination"]["total"] == 1
    assert data["items"][0][
        "trace_id"
    ] == "trace-5"
    assert data["items"][0]["cost"] is None


def test_usage_summary(
    isolated_usage_api_db,
):
    seed_usage(
        isolated_usage_api_db
    )

    response = TestClient(app).get(
        "/usage/summary"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["request_count"] == 5

    assert data["statuses"] == {
        "succeeded": 2,
        "provider_failed": 1,
        "client_disconnected": 1,
        "persistence_failed": 1,
    }

    assert data["usage_sources"] == {
        "provider_native": 2,
        "local_estimate": 2,
        "unavailable": 1,
    }

    assert data["prompt_tokens"] == 360
    assert data[
        "completion_tokens"
    ] == 165
    assert data["total_tokens"] == 525

    assert data[
        "total_latency_ms"
    ] == 150

    assert data[
        "average_latency_ms"
    ] == 30.0

    assert data["cost_statuses"] == {
        "estimated": 2,
        "unknown_price": 1,
        "usage_unavailable": 1,
        "missing_snapshot": 1,
    }

    assert data[
        "costs_by_currency"
    ] == [
        {
            "currency": "USD",
            "estimated_cost": (
                "0.000000000000"
            ),
        }
    ]


def test_daily_usage(
    isolated_usage_api_db,
):
    seed_usage(
        isolated_usage_api_db
    )

    response = TestClient(app).get(
        "/usage/daily"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["pagination"]["total"] == 3

    assert [
        (
            item["date"],
            item["request_count"],
        )
        for item in data["items"]
    ] == [
        ("2026-07-01", 2),
        ("2026-07-02", 2),
        ("2026-07-03", 1),
    ]


def test_provider_usage_aggregation(
    isolated_usage_api_db,
):
    seed_usage(
        isolated_usage_api_db
    )

    response = TestClient(app).get(
        "/usage/providers"
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert [
        (
            item["provider"],
            item["request_count"],
        )
        for item in items
    ] == [
        ("mock", 3),
        ("openai", 2),
    ]


def test_model_usage_aggregation_and_message_boundary(
    isolated_usage_api_db,
):
    seed_usage(
        isolated_usage_api_db
    )

    response = TestClient(app).get(
        "/usage/models"
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert [
        (
            item["provider"],
            item["model"],
            item["request_count"],
        )
        for item in items
    ] == [
        (
            "mock",
            "mock-shared",
            2,
        ),
        (
            "openai",
            "gpt-test",
            2,
        ),
        (
            "mock",
            "mock-failed",
            1,
        ),
    ]

    # 请求级成本不回写 Message。
    assert (
        "estimated_cost"
        not in Message.__table__.columns
    )
    assert (
        "pricing_version"
        not in Message.__table__.columns
    )
