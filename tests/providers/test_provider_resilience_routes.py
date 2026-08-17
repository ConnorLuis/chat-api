from __future__ import annotations

import json

from src.app.db.models import (
    UsageCost,
    UsageRecord,
)
from src.app.db.session import (
    get_session_factory,
)


PRIMARY_MODEL = "unreachable-primary-model"
FALLBACK_MODEL = "mock-fallback-model"


def configure_fallback(
    monkeypatch,
    tmp_path,
) -> None:
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:1",
    )
    monkeypatch.setenv(
        "OLLAMA_TIMEOUT_S",
        "0.05",
    )
    monkeypatch.setenv(
        "PROVIDER_RETRY_MAX_ATTEMPTS",
        "1",
    )
    monkeypatch.setenv(
        "PROVIDER_FALLBACK_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "PROVIDER_FALLBACK_PROVIDER",
        "mock",
    )
    monkeypatch.setenv(
        "PROVIDER_FALLBACK_MODEL",
        FALLBACK_MODEL,
    )
    monkeypatch.setenv(
        "RUN_LOG_PATH",
        str(tmp_path / "provider-runs.jsonl"),
    )


def assert_fallback_execution(
    execution: dict,
) -> None:
    assert execution["primary_provider"] == "ollama"
    assert execution["final_provider"] == "mock"
    assert execution["total_attempts"] == 2
    assert execution["retries"] == 0
    assert execution["fallback_used"] is True

    first, second = execution["attempts"]

    assert first["ordinal"] == 1
    assert first["provider"] == "ollama"
    assert first["model"] == PRIMARY_MODEL
    assert first["outcome"] == "failed"
    assert first["error_code"] == (
        "provider_connection_error"
    )
    assert first["retryable"] is True

    assert second["ordinal"] == 2
    assert second["provider"] == "mock"
    assert second["model"] == FALLBACK_MODEL
    assert second["outcome"] == "succeeded"


def assert_final_usage_and_cost(
    request_id: str,
) -> None:
    session_factory = get_session_factory()

    with session_factory() as session:
        usage = session.get(
            UsageRecord,
            request_id,
        )
        cost = session.get(
            UsageCost,
            request_id,
        )

    assert usage is not None
    assert usage.provider == "mock"
    assert usage.model == FALLBACK_MODEL

    assert cost is not None
    assert cost.pricing_key == (
        f"mock:{FALLBACK_MODEL}"
    )


def parse_named_sse(
    body: str,
) -> list[tuple[str, str]]:
    events = []
    normalized = body.replace("\r\n", "\n")

    for block in normalized.split("\n\n"):
        event_type = None
        data_lines = []

        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                data_lines.append(line[6:])

        if event_type is not None:
            events.append(
                (
                    event_type,
                    "\n".join(data_lines),
                )
            )

    return events


def parse_openai_sse(
    body: str,
) -> list[str]:
    events = []
    normalized = body.replace("\r\n", "\n")

    for block in normalized.split("\n\n"):
        data_lines = []

        for line in block.splitlines():
            if line.startswith("data: "):
                data_lines.append(line[6:])

        if data_lines:
            events.append("\n".join(data_lines))

    return events


def chat_payload() -> dict:
    return {
        "provider": "ollama",
        "model": PRIMARY_MODEL,
        "messages": [
            {
                "role": "user",
                "content": "fallback route test",
            }
        ],
        "max_tokens": 32,
    }


def openai_payload(
    *,
    stream: bool = False,
) -> dict:
    return {
        "provider": "ollama",
        "model": PRIMARY_MODEL,
        "messages": [
            {
                "role": "user",
                "content": "fallback route test",
            }
        ],
        "max_tokens": 32,
        "stream": stream,
    }


def test_chat_sync_exposes_final_fallback_execution(
    client,
    monkeypatch,
    tmp_path,
):
    configure_fallback(monkeypatch, tmp_path)

    response = client.post(
        "/chat",
        json=chat_payload(),
    )

    assert response.status_code == 200

    metadata = response.json()["metadata"]

    assert metadata["provider"] == "mock"
    assert metadata["model"] == FALLBACK_MODEL
    assert_fallback_execution(
        metadata["provider_execution"]
    )
    assert_final_usage_and_cost(
        metadata["usage"]["request_id"]
    )


def test_chat_stream_keeps_event_order_and_exposes_execution(
    client,
    monkeypatch,
    tmp_path,
):
    configure_fallback(monkeypatch, tmp_path)

    response = client.post(
        "/chat/stream",
        json=chat_payload(),
    )

    assert response.status_code == 200

    events = parse_named_sse(response.text)
    event_types = [
        event_type
        for event_type, _ in events
    ]

    assert event_types[0] == "meta"
    assert event_types[-2:] == ["usage", "done"]
    assert "error" not in event_types

    usage = json.loads(events[-2][1])

    assert usage["provider"] == "mock"
    assert usage["model"] == FALLBACK_MODEL
    assert_fallback_execution(
        usage["provider_execution"]
    )
    assert_final_usage_and_cost(
        usage["request_id"]
    )


def test_prompt_compare_exposes_execution_per_variant(
    client,
    monkeypatch,
    tmp_path,
):
    configure_fallback(monkeypatch, tmp_path)

    response = client.post(
        "/prompt/compare",
        json={
            **chat_payload(),
            "prompt_a": {
                "prompt_id": "chat",
                "prompt_version": "v1",
            },
            "prompt_b": {
                "prompt_id": "qa_strict",
                "prompt_version": "v1",
            },
        },
    )

    assert response.status_code == 200

    data = response.json()

    for variant in ("a", "b"):
        metadata = data[variant]["metadata"]
        assert metadata["provider"] == "mock"
        assert metadata["model"] == FALLBACK_MODEL
        assert_fallback_execution(
            metadata["provider_execution"]
        )


def test_openai_sync_exposes_gateway_execution(
    client,
    monkeypatch,
    tmp_path,
):
    configure_fallback(monkeypatch, tmp_path)

    response = client.post(
        "/v1/chat/completions",
        json=openai_payload(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["model"] == FALLBACK_MODEL
    assert_fallback_execution(
        data["gateway"][
            "provider_execution"
        ]
    )


def test_openai_stream_exposes_execution_on_finish_chunk(
    client,
    monkeypatch,
    tmp_path,
):
    configure_fallback(monkeypatch, tmp_path)

    response = client.post(
        "/v1/chat/completions",
        json=openai_payload(stream=True),
    )

    assert response.status_code == 200

    events = parse_openai_sse(response.text)

    assert events[-1] == "[DONE]"

    chunks = [
        json.loads(event)
        for event in events[:-1]
    ]
    finish_chunk = next(
        chunk
        for chunk in chunks
        if (
            chunk["choices"]
            and chunk["choices"][0][
                "finish_reason"
            ] is not None
        )
    )

    assert finish_chunk["model"] == FALLBACK_MODEL
    assert_fallback_execution(
        finish_chunk["gateway"][
            "provider_execution"
        ]
    )
