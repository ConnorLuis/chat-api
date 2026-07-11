from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    select,
)

from src.app.db.models import (
    UsageRecord,
)
from src.app.services import (
    NewUsageRecord,
)
from src.app.usage.persistence import (
    persist_usage_only,
)


def auth_headers(
    context,
) -> dict[str, str]:
    return {
        "X-API-Key": (
            context["api_key"]
        )
    }


def seed_usage(
    context,
    *,
    total_tokens: int,
) -> None:
    persist_usage_only(
        session_factory=(
            context["session_factory"]
        ),
        usage=NewUsageRecord(
            trace_id=(
                f"quota-seed-{uuid4()}"
            ),
            conversation_id=None,
            caller_key_id=(
                context["key_id"]
            ),
            request_kind="quota_seed",
            provider="mock",
            model="quota-seed-model",
            status="succeeded",
            usage_source="local_estimate",
            prompt_tokens=total_tokens,
            completion_tokens=0,
            total_tokens=total_tokens,
            latency_ms=1,
        ),
    )


def chat_payload(
    content: str = "day10 quota",
) -> dict:
    return {
        "provider": "mock",
        "model": "day10-quota-model",
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
    }


def test_disabled_quota_adds_no_headers(
    auth_context,
    monkeypatch,
):
    monkeypatch.setenv(
        "TOKEN_QUOTA_ENABLED",
        "false",
    )

    response = auth_context[
        "client"
    ].post(
        "/chat",
        headers=auth_headers(
            auth_context
        ),
        json=chat_payload(),
    )

    assert response.status_code == 200
    assert (
        "x-tokenquota-limit"
        not in response.headers
    )


def test_sync_chat_has_quota_headers_and_caller_usage(
    auth_context,
    monkeypatch,
):
    monkeypatch.setenv(
        "TOKEN_QUOTA_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "DAILY_TOKEN_QUOTA_TOKENS",
        "1000",
    )

    response = auth_context[
        "client"
    ].post(
        "/chat",
        headers=auth_headers(
            auth_context
        ),
        json=chat_payload(
            "sync caller accounting"
        ),
    )

    assert response.status_code == 200

    # Header 表示进入 Provider 前的 accounting 快照。
    assert response.headers[
        "x-tokenquota-limit"
    ] == "1000"
    assert response.headers[
        "x-tokenquota-used"
    ] == "0"
    assert response.headers[
        "x-tokenquota-remaining"
    ] == "1000"

    with auth_context[
        "session_factory"
    ]() as session:
        records = list(
            session.scalars(
                select(UsageRecord)
                .where(
                    UsageRecord
                    .caller_key_id
                    == auth_context[
                        "key_id"
                    ],
                    UsageRecord
                    .request_kind
                    == "chat_sync",
                )
            ).all()
        )

    assert len(records) == 1
    assert records[0].total_tokens is not None
    assert records[0].total_tokens > 0


def test_daily_quota_returns_native_429(
    auth_context,
    monkeypatch,
):
    monkeypatch.setenv(
        "TOKEN_QUOTA_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "DAILY_TOKEN_QUOTA_TOKENS",
        "100",
    )

    seed_usage(
        auth_context,
        total_tokens=100,
    )

    response = auth_context[
        "client"
    ].post(
        "/chat",
        headers=auth_headers(
            auth_context
        ),
        json=chat_payload(
            "must be rejected"
        ),
    )

    assert response.status_code == 429
    assert response.json() == {
        "detail": {
            "code": (
                "daily_token_quota_exceeded"
            ),
            "message": (
                "Daily token quota exceeded"
            ),
        }
    }

    assert response.headers[
        "x-tokenquota-limit"
    ] == "100"
    assert response.headers[
        "x-tokenquota-used"
    ] == "100"
    assert response.headers[
        "x-tokenquota-remaining"
    ] == "0"

    assert int(
        response.headers["retry-after"]
    ) >= 1

    with auth_context[
        "session_factory"
    ]() as session:
        chat_count = len(
            list(
                session.scalars(
                    select(UsageRecord)
                    .where(
                        UsageRecord
                        .caller_key_id
                        == auth_context[
                            "key_id"
                        ],
                        UsageRecord
                        .request_kind
                        == "chat_sync",
                    )
                ).all()
            )
        )

    # Provider 未被调用，因此没有新的 chat_sync usage。
    assert chat_count == 0


def test_stream_chat_persists_caller_usage(
    auth_context,
    monkeypatch,
):
    monkeypatch.setenv(
        "TOKEN_QUOTA_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "DAILY_TOKEN_QUOTA_TOKENS",
        "1000",
    )

    response = auth_context[
        "client"
    ].post(
        "/chat/stream",
        headers=auth_headers(
            auth_context
        ),
        json=chat_payload(
            "stream caller accounting"
        ),
    )

    assert response.status_code == 200
    assert "event: done" in response.text

    assert response.headers[
        "x-tokenquota-limit"
    ] == "1000"

    with auth_context[
        "session_factory"
    ]() as session:
        records = list(
            session.scalars(
                select(UsageRecord)
                .where(
                    UsageRecord
                    .caller_key_id
                    == auth_context[
                        "key_id"
                    ],
                    UsageRecord
                    .request_kind
                    == "chat_stream",
                )
            ).all()
        )

    assert len(records) == 1
    assert records[0].total_tokens is not None


def test_usage_reporting_is_not_blocked_by_quota(
    auth_context,
    monkeypatch,
):
    monkeypatch.setenv(
        "TOKEN_QUOTA_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "DAILY_TOKEN_QUOTA_TOKENS",
        "10",
    )

    seed_usage(
        auth_context,
        total_tokens=10,
    )

    response = auth_context[
        "client"
    ].get(
        "/usage/summary",
        headers=auth_headers(
            auth_context
        ),
    )

    assert response.status_code == 200


def test_auth_disabled_skips_user_token_quota(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "API_AUTH_ENABLED",
        "false",
    )
    monkeypatch.setenv(
        "TOKEN_QUOTA_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "DAILY_TOKEN_QUOTA_TOKENS",
        "1",
    )

    response = client.post(
        "/chat",
        json=chat_payload(
            "compatibility mode"
        ),
    )

    assert response.status_code == 200
    assert (
        "x-tokenquota-limit"
        not in response.headers
    )
