from __future__ import annotations

import json

import pytest

from scripts.docker_smoke_test import (
    SmokeTestError,
    build_headers,
    normalize_base_url,
    parse_json_object,
    parse_sse,
    run_smoke_test,
    validate_native_stream,
    validate_openai_stream,
)


def native_stream_body() -> str:
    return "\n\n".join(
        [
            'event: meta\ndata: {"provider":"mock"}',
            "event: token\ndata: hello",
            'event: usage\ndata: {"status":"succeeded"}',
            "event: done\ndata: [DONE]",
            "",
        ]
    )


def openai_stream_body() -> str:
    chunks = [
        {
            "object": "chat.completion.chunk",
            "choices": [
                {
                    "delta": {"role": "assistant"},
                    "finish_reason": None,
                }
            ],
        },
        {
            "object": "chat.completion.chunk",
            "choices": [
                {
                    "delta": {"content": "hello"},
                    "finish_reason": None,
                }
            ],
        },
        {
            "object": "chat.completion.chunk",
            "choices": [
                {
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        },
    ]
    blocks = [
        f"data: {json.dumps(chunk)}"
        for chunk in chunks
    ]
    blocks.extend(["data: [DONE]", ""])
    return "\n\n".join(blocks)


@pytest.mark.parametrize(
    "value",
    [
        "localhost:8000",
        "ftp://localhost:8000",
        "http://localhost:8000/api",
        "http://localhost:8000?debug=true",
    ],
)
def test_normalize_base_url_rejects_non_origin(value):
    with pytest.raises(SmokeTestError, match=r"HTTP\(S\) origin"):
        normalize_base_url(value)


def test_normalize_base_url_removes_trailing_slash():
    assert normalize_base_url(
        " http://127.0.0.1:8000/ "
    ) == "http://127.0.0.1:8000"


def test_build_headers_only_adds_non_empty_api_key():
    public_headers = build_headers(trace_id="public")
    protected_headers = build_headers(
        trace_id="protected",
        api_key="secret-key",
    )

    assert "X-API-Key" not in public_headers
    assert protected_headers["X-API-Key"] == "secret-key"
    assert protected_headers["X-Trace-Id"] == "protected"


def test_sse_validators_accept_release_contracts():
    validate_native_stream(native_stream_body())
    validate_openai_stream(openai_stream_body())

    assert parse_sse("data: first\r\n\r\ndata: second") == [
        (None, "first"),
        (None, "second"),
    ]


def test_native_stream_rejects_semantic_error_event():
    body = "\n\n".join(
        [
            'event: meta\ndata: {"provider":"mock"}',
            'event: error\ndata: {"code":"provider_error"}',
            "",
        ]
    )

    with pytest.raises(SmokeTestError, match="event:error"):
        validate_native_stream(body)


def test_native_stream_rejects_invalid_event_order():
    body = "\n\n".join(
        [
            'event: meta\ndata: {"provider":"mock"}',
            'event: usage\ndata: {"status":"succeeded"}',
            "event: token\ndata: too-late",
            "event: done\ndata: [DONE]",
            "",
        ]
    )

    with pytest.raises(
        SmokeTestError,
        match="usage immediately before done",
    ):
        validate_native_stream(body)


def test_native_stream_requires_successful_usage():
    body = native_stream_body().replace(
        '"status":"succeeded"',
        '"status":"provider_failed"',
    )

    with pytest.raises(SmokeTestError, match="usage did not succeed"):
        validate_native_stream(body)


def test_openai_stream_requires_done_marker():
    body = openai_stream_body().replace(
        "\n\ndata: [DONE]",
        "",
    )

    with pytest.raises(SmokeTestError, match=r"data: \[DONE\]"):
        validate_openai_stream(body)


def test_parse_json_object_rejects_non_object():
    with pytest.raises(SmokeTestError, match="JSON object"):
        parse_json_object("[]", label="test")


def test_run_smoke_test_checks_all_release_routes():
    calls: list[tuple[str, dict]] = []

    def requester(
        _base_url: str,
        path: str,
        **kwargs,
    ) -> tuple[int, str]:
        calls.append((path, kwargs))

        if path == "/ready":
            return 200, '{"status":"ready"}'
        if path == "/health":
            return 200, '{"status":"ok"}'
        if path == "/chat/stream":
            return 200, native_stream_body()
        if path == "/chat":
            return 200, json.dumps(
                {
                    "answer": "ok",
                    "metadata": {"provider": "mock"},
                }
            )
        if path == "/v1/chat/completions":
            if kwargs["payload"].get("stream"):
                return 200, openai_stream_body()
            return 200, json.dumps(
                {
                    "object": "chat.completion",
                    "choices": [{"message": {"content": "ok"}}],
                }
            )

        raise AssertionError(f"unexpected path: {path}")

    run_smoke_test(
        "http://test",
        wait_timeout_seconds=1,
        request_timeout_seconds=1,
        api_key="smoke-key",
        requester=requester,
    )

    assert [path for path, _kwargs in calls] == [
        "/ready",
        "/health",
        "/chat",
        "/chat/stream",
        "/v1/chat/completions",
        "/v1/chat/completions",
    ]

    protected_calls = calls[2:]
    assert all(
        kwargs["api_key"] == "smoke-key"
        for _path, kwargs in protected_calls
    )
    assert all(
        kwargs["method"] == "POST"
        for _path, kwargs in protected_calls
    )
