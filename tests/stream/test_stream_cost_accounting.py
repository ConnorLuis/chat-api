from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.requests import Request

from src.app.api import (
    routes_chat as routes_module,
)
from src.app.db.models import (
    UsageCost,
    UsageRecord,
)
from src.app.llm.providers import (
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
)
from src.app.llm.schemas import ChatRequest
from src.app.main import app


def parse_sse_events(
    body: str,
) -> list[tuple[str, str]]:
    events = []

    for block in body.replace(
        "\r\n",
        "\n",
    ).split("\n\n"):
        event_name = None
        data_lines = []

        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = (
                    line[len("event:"):]
                    .removeprefix(" ")
                )

            elif line.startswith("data:"):
                data_lines.append(
                    line[len("data:"):]
                    .removeprefix(" ")
                )

        if event_name is not None:
            events.append(
                (
                    event_name,
                    "\n".join(data_lines),
                )
            )

    return events


class PartialFailureProvider:
    name = "mock"

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return requested_model or "partial-model"

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        raise AssertionError

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        yield ProviderChatChunk(
            delta="partial",
            provider=self.name,
            model=self.resolve_model(
                request.model
            ),
        )

        raise RuntimeError(
            "forced partial stream failure"
        )


class DisconnectCostProvider:
    name = "mock"

    def __init__(self) -> None:
        self.closed = False

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return (
            requested_model
            or "disconnect-cost-model"
        )

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        raise AssertionError

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        try:
            yield ProviderChatChunk(
                delta="partial",
                provider=self.name,
                model=self.resolve_model(
                    request.model
                ),
            )

            await asyncio.Event().wait()

        finally:
            self.closed = True


def load_cost(
    session_factory,
):
    with session_factory() as session:
        usage = session.scalars(
            select(UsageRecord)
        ).one()

        cost = session.scalars(
            select(UsageCost)
        ).one()

    return usage, cost


def test_partial_stream_failure_has_estimated_zero_cost(
    isolated_stream_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_stream_accounting_db
    )

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: PartialFailureProvider(),
    )

    response = TestClient(app).post(
        "/chat/stream",
        json={
            "provider": "mock",
            "model": "partial-model",
            "messages": [
                {
                    "role": "user",
                    "content": "partial failure",
                }
            ],
        },
    )

    events = parse_sse_events(
        response.text
    )

    assert [
        name
        for name, _ in events
    ] == [
        "meta",
        "token",
        "error",
    ]

    error = json.loads(
        events[-1][1]
    )

    cost = error["usage"]["cost"]

    assert cost["cost_status"] == (
        "estimated"
    )
    assert cost["pricing_key"] == (
        "mock:partial-model"
    )
    assert cost[
        "matched_pricing_key"
    ] == "mock:*"
    assert cost["estimated_cost"] == (
        "0.000000000000"
    )

    usage_record, cost_record = (
        load_cost(session_factory)
    )

    assert usage_record.status == (
        "provider_failed"
    )
    assert usage_record.usage_source == (
        "local_estimate"
    )
    assert cost_record.cost_status == (
        "estimated"
    )


def test_stream_disconnect_persists_estimated_cost(
    isolated_stream_accounting_db,
    monkeypatch,
):
    session_factory = (
        isolated_stream_accounting_db
    )

    provider = DisconnectCostProvider()

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        lambda _: provider,
    )
    monkeypatch.setattr(
        routes_module,
        "get_trace_id",
        lambda _: "cost-disconnect-trace",
    )

    async def run_disconnect():
        scope = {
            "type": "http",
            "asgi": {
                "version": "3.0",
            },
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/chat/stream",
            "raw_path": b"/chat/stream",
            "query_string": b"",
            "headers": [],
            "client": (
                "testclient",
                50000,
            ),
            "server": (
                "testserver",
                80,
            ),
        }

        request = Request(scope)

        response = await (
            routes_module.chat_stream(
                request,
                ChatRequest(
                    provider="mock",
                    model=(
                        "disconnect-cost-model"
                    ),
                    messages=[
                        {
                            "role": "user",
                            "content": "disconnect",
                        }
                    ],
                ),
            )
        )

        iterator = response.body_iterator

        await anext(iterator)
        await anext(iterator)

        await iterator.aclose()

    asyncio.run(run_disconnect())

    assert provider.closed is True

    usage_record, cost_record = (
        load_cost(session_factory)
    )

    assert usage_record.trace_id == (
        "cost-disconnect-trace"
    )
    assert usage_record.status == (
        "client_disconnected"
    )
    assert cost_record.cost_status == (
        "estimated"
    )
    assert str(
        cost_record.estimated_cost
    ) == "0E-12"
