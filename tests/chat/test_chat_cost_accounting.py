from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from sqlalchemy import select

from src.app.api import (
    routes_chat as routes_module,
)
from src.app.db.models import (
    Message,
    UsageCost,
    UsageRecord,
)
from src.app.llm.providers import (
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderUsage,
)
from src.app.main import app


class SyncCostProvider:
    def __init__(
        self,
        *,
        name: str,
        usage: ProviderUsage | None,
        fail: bool = False,
    ) -> None:
        self.name = name
        self.usage = usage
        self.fail = fail

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return requested_model or "cost-model"

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        if self.fail:
            raise RuntimeError(
                "forced cost provider failure"
            )

        return ProviderChatResponse(
            content="cost answer",
            provider=self.name,
            model=self.resolve_model(
                request.model
            ),
            usage=self.usage,
            finish_reason="stop",
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        raise AssertionError
        yield


def load_rows(
    session_factory,
):
    with session_factory() as session:
        usage = list(
            session.scalars(
                select(UsageRecord)
            ).all()
        )
        costs = list(
            session.scalars(
                select(UsageCost)
            ).all()
        )

    return usage, costs


def test_sync_zero_price_cost_is_exposed_and_persisted(
    isolated_chat_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_chat_accounting_db
    )

    provider = SyncCostProvider(
        name="mock",
        usage=ProviderUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        ),
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )

    response = TestClient(app).post(
        "/chat",
        json={
            "provider": "mock",
            "model": "mock-paid-boundary",
            "messages": [
                {
                    "role": "user",
                    "content": "cost",
                }
            ],
        },
    )

    assert response.status_code == 200

    cost = response.json()[
        "metadata"
    ]["usage"]["cost"]

    assert cost["cost_status"] == (
        "estimated"
    )
    assert cost["pricing_key"] == (
        "mock:mock-paid-boundary"
    )
    assert cost[
        "matched_pricing_key"
    ] == "mock:*"
    assert cost["pricing_version"] == (
        "2026-07-11-v1"
    )
    assert cost["currency"] == "USD"
    assert cost["unit_tokens"] == (
        1_000_000
    )
    assert cost["prompt_cost"] == (
        "0.000000000000"
    )
    assert cost["completion_cost"] == (
        "0.000000000000"
    )
    assert cost["estimated_cost"] == (
        "0.000000000000"
    )

    usage_rows, cost_rows = load_rows(
        session_factory
    )

    assert len(usage_rows) == 1
    assert len(cost_rows) == 1
    assert cost_rows[0].request_id == (
        usage_rows[0].request_id
    )

    # 请求级 cost 不回写 Message。
    assert (
        "estimated_cost"
        not in Message.__table__.columns
    )


def test_sync_unknown_price_is_null_not_zero(
    isolated_chat_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_chat_accounting_db
    )

    provider = SyncCostProvider(
        name="openai",
        usage=ProviderUsage(
            prompt_tokens=10,
            completion_tokens=4,
            total_tokens=14,
        ),
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )

    response = TestClient(app).post(
        "/chat",
        json={
            "provider": "openai",
            "model": "unpriced-model",
            "messages": [
                {
                    "role": "user",
                    "content": "unknown price",
                }
            ],
        },
    )

    assert response.status_code == 200

    cost = response.json()[
        "metadata"
    ]["usage"]["cost"]

    assert cost["cost_status"] == (
        "unknown_price"
    )
    assert cost["pricing_key"] == (
        "openai:unpriced-model"
    )
    assert (
        cost["matched_pricing_key"]
        is None
    )
    assert cost["prompt_cost"] is None
    assert (
        cost["completion_cost"]
        is None
    )
    assert cost["estimated_cost"] is None

    _, cost_rows = load_rows(
        session_factory
    )

    assert len(cost_rows) == 1
    assert cost_rows[0].cost_status == (
        "unknown_price"
    )
    assert (
        cost_rows[0].estimated_cost
        is None
    )


def test_sync_provider_failure_records_unavailable_cost(
    isolated_chat_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_chat_accounting_db
    )

    provider = SyncCostProvider(
        name="openai",
        usage=None,
        fail=True,
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )

    response = TestClient(app).post(
        "/chat",
        json={
            "provider": "openai",
            "model": "failed-model",
            "messages": [
                {
                    "role": "user",
                    "content": "fail",
                }
            ],
        },
    )

    assert response.status_code == 502

    usage_rows, cost_rows = load_rows(
        session_factory
    )

    assert len(usage_rows) == 1
    assert usage_rows[0].status == (
        "provider_failed"
    )

    assert len(cost_rows) == 1
    assert cost_rows[0].cost_status == (
        "usage_unavailable"
    )
    assert (
        cost_rows[0].estimated_cost
        is None
    )
