from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    ProxyHandler,
    Request,
    build_opener,
)


class SmokeTestError(RuntimeError):
    """The release container did not satisfy its public HTTP contract."""


HttpRequester = Callable[..., tuple[int, str]]


def normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise SmokeTestError(
            "base URL must be an HTTP(S) origin without a path, "
            "query, or fragment"
        )

    return normalized


def build_headers(
    *,
    trace_id: str,
    api_key: str = "",
) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "X-Trace-Id": trace_id,
    }

    if api_key:
        headers["X-API-Key"] = api_key

    return headers


def http_request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 10.0,
    trace_id: str,
    api_key: str = "",
) -> tuple[int, str]:
    body = None

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = Request(
        f"{base_url}{path}",
        data=body,
        headers=build_headers(
            trace_id=trace_id,
            api_key=api_key,
        ),
        method=method,
    )

    # Local release checks must not be redirected through ambient proxies.
    opener = build_opener(ProxyHandler({}))

    try:
        with opener.open(
            request,
            timeout=timeout_seconds,
        ) as response:
            status = int(response.status)
            response_body = response.read().decode(
                "utf-8",
                errors="replace",
            )

    except HTTPError as exc:
        error_body = exc.read().decode(
            "utf-8",
            errors="replace",
        )
        raise SmokeTestError(
            f"{method} {path} returned HTTP {exc.code}: "
            f"{error_body[:500]}"
        ) from exc

    except URLError as exc:
        raise SmokeTestError(
            f"{method} {path} connection failed: {exc.reason}"
        ) from exc

    except OSError as exc:
        raise SmokeTestError(
            f"{method} {path} connection failed: {exc}"
        ) from exc

    if not 200 <= status < 300:
        raise SmokeTestError(
            f"{method} {path} returned HTTP {status}: "
            f"{response_body[:500]}"
        )

    return status, response_body


def parse_json_object(
    body: str,
    *,
    label: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SmokeTestError(
            f"{label} returned invalid JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise SmokeTestError(
            f"{label} must return a JSON object"
        )

    return payload


def parse_sse(body: str) -> list[tuple[str | None, str]]:
    normalized = body.replace("\r\n", "\n")
    events: list[tuple[str | None, str]] = []

    for raw_block in normalized.split("\n\n"):
        block = raw_block.strip("\n")

        if not block:
            continue

        event_name: str | None = None
        data_lines: list[str] = []

        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                value = line[len("data:"):]
                if value.startswith(" "):
                    value = value[1:]
                data_lines.append(value)

        if data_lines:
            events.append(
                (event_name, "\n".join(data_lines))
            )

    return events


def validate_native_stream(body: str) -> None:
    events = parse_sse(body)
    event_names = [name for name, _data in events]

    if not events:
        raise SmokeTestError("native stream returned no SSE events")

    if event_names[0] != "meta":
        raise SmokeTestError(
            "native stream must start with event: meta"
        )

    if "error" in event_names:
        index = event_names.index("error")
        raise SmokeTestError(
            f"native stream returned event:error: {events[index][1][:500]}"
        )

    if len(events) < 4:
        raise SmokeTestError(
            "native stream returned no token event"
        )

    if events[-1] != ("done", "[DONE]"):
        raise SmokeTestError(
            "native stream must terminate with event: done / [DONE]"
        )

    if event_names[-2] != "usage":
        raise SmokeTestError(
            "native stream must emit usage immediately before done"
        )

    token_event_names = event_names[1:-2]

    if not token_event_names:
        raise SmokeTestError(
            "native stream returned no token event"
        )

    if any(
        event_name != "token"
        for event_name in token_event_names
    ):
        raise SmokeTestError(
            "native stream event order must be "
            "meta -> token+ -> usage -> done"
        )

    meta = parse_json_object(
        events[0][1],
        label="native stream meta event",
    )
    usage = parse_json_object(
        events[-2][1],
        label="native stream usage event",
    )

    if not meta.get("provider"):
        raise SmokeTestError(
            "native stream meta event is missing provider"
        )

    if usage.get("status") != "succeeded":
        raise SmokeTestError(
            f"native stream usage did not succeed: {usage}"
        )


def validate_openai_stream(body: str) -> None:
    events = parse_sse(body)

    if not events or events[-1][1] != "[DONE]":
        raise SmokeTestError(
            "OpenAI-compatible stream must terminate with data: [DONE]"
        )

    chunks: list[dict[str, Any]] = []

    for _event_name, data in events[:-1]:
        chunk = parse_json_object(
            data,
            label="OpenAI-compatible stream chunk",
        )
        chunks.append(chunk)

    if not chunks:
        raise SmokeTestError(
            "OpenAI-compatible stream returned no JSON chunks"
        )

    if any(
        chunk.get("object") != "chat.completion.chunk"
        for chunk in chunks
    ):
        raise SmokeTestError(
            "OpenAI-compatible stream returned an invalid object type"
        )

    content = "".join(
        choice.get("delta", {}).get("content", "")
        for chunk in chunks
        for choice in chunk.get("choices", [])
    )

    if not content:
        raise SmokeTestError(
            "OpenAI-compatible stream returned no content delta"
        )

    if not any(
        choice.get("finish_reason") is not None
        for chunk in chunks
        for choice in chunk.get("choices", [])
    ):
        raise SmokeTestError(
            "OpenAI-compatible stream returned no finish chunk"
        )


def wait_until_ready(
    base_url: str,
    *,
    wait_timeout_seconds: float,
    request_timeout_seconds: float,
    requester: HttpRequester = http_request,
) -> None:
    deadline = time.monotonic() + wait_timeout_seconds
    last_error = "service has not responded"
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1

        try:
            _status, body = requester(
                base_url,
                "/ready",
                timeout_seconds=request_timeout_seconds,
                trace_id=f"docker-smoke-ready-{attempt}",
            )
            payload = parse_json_object(
                body,
                label="GET /ready",
            )

            if payload.get("status") == "ready":
                return

            last_error = f"unexpected readiness payload: {payload}"

        except SmokeTestError as exc:
            last_error = str(exc)

        time.sleep(1.0)

    raise SmokeTestError(
        "service did not become ready within "
        f"{wait_timeout_seconds:g}s: {last_error}"
    )


def run_smoke_test(
    base_url: str,
    *,
    wait_timeout_seconds: float = 90.0,
    request_timeout_seconds: float = 10.0,
    api_key: str = "",
    requester: HttpRequester = http_request,
) -> None:
    wait_until_ready(
        base_url,
        wait_timeout_seconds=wait_timeout_seconds,
        request_timeout_seconds=request_timeout_seconds,
        requester=requester,
    )
    print("[pass] GET /ready")

    _status, body = requester(
        base_url,
        "/health",
        timeout_seconds=request_timeout_seconds,
        trace_id="docker-smoke-health",
    )
    health = parse_json_object(
        body,
        label="GET /health",
    )
    if health.get("status") != "ok":
        raise SmokeTestError(
            f"unexpected health payload: {health}"
        )
    print("[pass] GET /health")

    native_payload = {
        "provider": "mock",
        "model": "docker-smoke-model",
        "messages": [
            {
                "role": "user",
                "content": "docker smoke",
            }
        ],
        "max_tokens": 32,
    }

    _status, body = requester(
        base_url,
        "/chat",
        method="POST",
        payload=native_payload,
        timeout_seconds=request_timeout_seconds,
        trace_id="docker-smoke-native-sync",
        api_key=api_key,
    )
    native_response = parse_json_object(
        body,
        label="POST /chat",
    )
    if (
        not native_response.get("answer")
        or native_response.get("metadata", {}).get("provider") != "mock"
    ):
        raise SmokeTestError(
            f"unexpected native chat payload: {native_response}"
        )
    print("[pass] POST /chat")

    _status, body = requester(
        base_url,
        "/chat/stream",
        method="POST",
        payload=native_payload,
        timeout_seconds=request_timeout_seconds,
        trace_id="docker-smoke-native-stream",
        api_key=api_key,
    )
    validate_native_stream(body)
    print("[pass] POST /chat/stream")

    openai_payload = {
        "provider": "mock",
        "model": "docker-smoke-model",
        "messages": [
            {
                "role": "user",
                "content": "docker smoke",
            }
        ],
        "max_tokens": 32,
    }

    _status, body = requester(
        base_url,
        "/v1/chat/completions",
        method="POST",
        payload=openai_payload,
        timeout_seconds=request_timeout_seconds,
        trace_id="docker-smoke-openai-sync",
        api_key=api_key,
    )
    openai_response = parse_json_object(
        body,
        label="POST /v1/chat/completions",
    )
    if (
        openai_response.get("object") != "chat.completion"
        or not openai_response.get("choices")
    ):
        raise SmokeTestError(
            "OpenAI-compatible sync response contract failed"
        )
    print("[pass] POST /v1/chat/completions")

    stream_payload = {
        **openai_payload,
        "stream": True,
    }
    _status, body = requester(
        base_url,
        "/v1/chat/completions",
        method="POST",
        payload=stream_payload,
        timeout_seconds=request_timeout_seconds,
        trace_id="docker-smoke-openai-stream",
        api_key=api_key,
    )
    validate_openai_stream(body)
    print("[pass] POST /v1/chat/completions stream=true")


def build_argument_parser() -> argparse.ArgumentParser:
    default_port = os.getenv("CHAT_API_PORT", "8000")
    parser = argparse.ArgumentParser(
        description=(
            "Wait for the release container and verify health, readiness, "
            "native chat, native SSE, and OpenAI-compatible sync/stream."
        )
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv(
            "CHAT_API_BASE_URL",
            f"http://127.0.0.1:{default_port}",
        ),
    )
    parser.add_argument(
        "--wait-timeout-seconds",
        type=float,
        default=90.0,
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=10.0,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)

    try:
        if args.wait_timeout_seconds <= 0:
            raise ValueError(
                "wait timeout must be greater than zero"
            )
        if args.request_timeout_seconds <= 0:
            raise ValueError(
                "request timeout must be greater than zero"
            )

        base_url = normalize_base_url(args.base_url)
        run_smoke_test(
            base_url,
            wait_timeout_seconds=args.wait_timeout_seconds,
            request_timeout_seconds=args.request_timeout_seconds,
            api_key=os.getenv("CHAT_API_KEY", "").strip(),
        )

    except (SmokeTestError, ValueError) as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 1

    print(f"Docker smoke test passed: {base_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
