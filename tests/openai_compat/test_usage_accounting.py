from __future__ import annotations

from sqlalchemy import select

from src.app.db.models import (
    UsageCost,
    UsageRecord,
)


def auth_headers(
    context,
) -> dict[str, str]:
    return {
        "Authorization": (
            f"Bearer {context['api_key']}"
        )
    }


def payload(
    *,
    provider: str = "mock",
) -> dict:
    return {
        "provider": provider,
        "model": "openai-accounting-model",
        "messages": [
            {
                "role": "user",
                "content": (
                    "OpenAI accounting test"
                ),
            }
        ],
    }


def load_records(
    context,
) -> list[UsageRecord]:
    with context[
        "session_factory"
    ]() as session:
        return list(
            session.scalars(
                select(UsageRecord)
                .where(
                    UsageRecord.request_kind
                    == (
                        "openai_chat_"
                        "completions_sync"
                    )
                )
                .order_by(
                    UsageRecord
                    .created_at
                    .asc()
                )
            ).all()
        )


def test_openai_sync_persists_caller_usage_and_cost(
    auth_context,
):
    response = auth_context[
        "client"
    ].post(
        "/v1/chat/completions",
        headers=auth_headers(
            auth_context
        ),
        json=payload(),
    )

    assert response.status_code == 200

    records = load_records(
        auth_context
    )

    assert len(records) == 1

    record = records[0]

    assert (
        record.caller_key_id
        == auth_context["key_id"]
    )
    assert record.status == "succeeded"
    assert (
        record.usage_source
        == "local_estimate"
    )
    assert record.total_tokens is not None
    assert record.total_tokens > 0

    with auth_context[
        "session_factory"
    ]() as session:
        cost = session.get(
            UsageCost,
            record.request_id,
        )

    assert cost is not None


def test_openai_response_contract_still_omits_mock_usage(
    auth_context,
):
    response = auth_context[
        "client"
    ].post(
        "/v1/chat/completions",
        headers=auth_headers(
            auth_context
        ),
        json=payload(),
    )

    assert response.status_code == 200

    # 内部 accounting 可以使用 local estimate，
    # 但 OpenAI response 不伪造 Provider 原生 usage。
    assert "usage" not in response.json()


def test_openai_provider_failure_persists_usage_fact(
    auth_context,
    monkeypatch,
):
    monkeypatch.delenv(
        "OPENAI_API_KEY",
        raising=False,
    )
    monkeypatch.delenv(
        "OPENAI_BASE_URL",
        raising=False,
    )

    response = auth_context[
        "client"
    ].post(
        "/v1/chat/completions",
        headers=auth_headers(
            auth_context
        ),
        json=payload(
            provider="openai"
        ),
    )

    assert response.status_code == 502

    records = load_records(
        auth_context
    )

    assert len(records) == 1

    record = records[0]

    assert (
        record.caller_key_id
        == auth_context["key_id"]
    )
    assert (
        record.status
        == "provider_failed"
    )
    assert (
        record.usage_source
        == "unavailable"
    )
    assert record.total_tokens is None

    with auth_context[
        "session_factory"
    ]() as session:
        cost = session.get(
            UsageCost,
            record.request_id,
        )

    assert cost is not None
    assert (
        cost.cost_status
        == "usage_unavailable"
    )
