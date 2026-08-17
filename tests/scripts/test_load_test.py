import asyncio
from pathlib import Path

import httpx
import pytest

from scripts.load_test import (
    LoadTestConfigError,
    RequestSample,
    build_request_payload,
    execute_request,
    load_suite_config,
    native_sse_outcome,
    openai_sse_outcome,
    parse_sse_block,
    parse_suite_config,
    percentile,
    render_markdown_report,
    summarize_samples,
)


def suite_payload():
    return {
        "suite_name": "unit",
        "base_url": "http://test",
        "defaults": {
            "provider": "mock",
            "model": "mock-load",
            "prompt": "ping",
            "max_tokens": 16,
            "timeout_s": 5,
            "warmup_requests": 1,
        },
        "scenarios": [
            {
                "name": "native",
                "mode": "native_sync",
                "requests": 4,
                "concurrency": 2,
            },
            {
                "name": "openai-stream",
                "mode": "openai_stream",
                "requests": 2,
                "concurrency": 1,
            },
        ],
    }


def test_parse_suite_config_merges_defaults():
    suite = parse_suite_config(suite_payload())

    assert suite.suite_name == "unit"
    assert suite.base_url == "http://test"
    assert len(suite.scenarios) == 2
    assert suite.scenarios[0].provider == "mock"
    assert suite.scenarios[0].max_tokens == 16
    assert suite.scenarios[1].is_streaming is True


@pytest.mark.parametrize(
    "path",
    [
        "benchmarks/configs/mock_baseline.json",
        "benchmarks/configs/ollama_baseline.example.json",
    ],
)
def test_committed_benchmark_configs_are_valid(path):
    suite = load_suite_config(Path(path))

    assert suite.scenarios


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload.update({"typo": True}),
            "unknown fields",
        ),
        (
            lambda payload: payload["scenarios"][1].update(
                {"name": "native"}
            ),
            "must be unique",
        ),
        (
            lambda payload: payload["scenarios"][0].update(
                {"concurrency": 5}
            ),
            "cannot exceed requests",
        ),
        (
            lambda payload: payload["scenarios"][1].update(
                {"model": None}
            ),
            "requires model",
        ),
    ],
)
def test_parse_suite_config_rejects_invalid_values(
    mutate,
    message,
):
    payload = suite_payload()
    mutate(payload)

    with pytest.raises(LoadTestConfigError, match=message):
        parse_suite_config(payload)


def test_percentile_uses_linear_interpolation():
    values = [10.0, 20.0, 30.0, 40.0]

    assert percentile(values, 0.50) == 25.0
    assert percentile(values, 0.95) == pytest.approx(38.5)
    assert percentile([7.0], 0.95) == 7.0
    assert percentile([], 0.95) is None


def test_summarize_samples_reports_required_metrics():
    samples = [
        RequestSample(
            index=0,
            trace_id="a",
            success=True,
            status_code=200,
            latency_ms=10,
            ttft_ms=4,
            response_bytes=20,
            token_events=2,
        ),
        RequestSample(
            index=1,
            trace_id="b",
            success=True,
            status_code=200,
            latency_ms=20,
            ttft_ms=8,
            response_bytes=22,
            token_events=3,
        ),
        RequestSample(
            index=2,
            trace_id="c",
            success=False,
            status_code=503,
            latency_ms=30,
            ttft_ms=None,
            response_bytes=10,
            token_events=0,
            error_kind="http_503",
            error_message="unavailable",
        ),
    ]

    summary = summarize_samples(samples, wall_seconds=0.5)

    assert summary["throughput_rps"] == 6.0
    assert summary["error_rate_percent"] == pytest.approx(33.333)
    assert summary["latency_ms"]["p50"] == 20.0
    assert summary["latency_ms"]["p95"] == pytest.approx(29.0)
    assert summary["ttft_ms"]["p50"] == 6.0
    assert summary["status_counts"] == {"200": 2, "503": 1}
    assert summary["error_counts"] == {"http_503": 1}
    assert summary["error_examples"] == {
        "http_503": "unavailable"
    }


def test_request_payloads_match_both_api_contracts():
    suite = parse_suite_config(suite_payload())

    native_path, native = build_request_payload(
        suite.scenarios[0]
    )
    openai_path, openai = build_request_payload(
        suite.scenarios[1]
    )

    assert native_path == "/chat"
    assert native["provider"] == "mock"
    assert native["use_kb"] is False
    assert openai_path == "/v1/chat/completions"
    assert openai["stream"] is True
    assert openai["stream_options"] == {"include_usage": True}


def test_sse_parsers_require_explicit_terminal_events():
    event, data = parse_sse_block(
        ["event: token", "data: hello"]
    )
    token, done, error = native_sse_outcome(event, data)

    assert (token, done, error) == ("hello", False, None)
    assert native_sse_outcome("done", "[DONE]") == (
        None,
        True,
        None,
    )
    assert openai_sse_outcome("[DONE]") == (
        None,
        True,
        None,
    )
    token, done, error = openai_sse_outcome(
        '{"choices":[{"delta":{"content":"hi"}}]}'
    )
    assert (token, done, error) == ("hi", False, None)

    token, done, error = openai_sse_outcome(
        '{"error":{"code":"provider_timeout"}}'
    )
    assert token is None
    assert done is False
    assert "provider_timeout" in error


def test_execute_request_counts_valid_native_stream():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-trace-id"].startswith("load-run-")
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=(
                "event: meta\n"
                "data: {}\n\n"
                "event: token\n"
                "data: h\n\n"
                "event: token\n"
                "data: i\n\n"
                "event: done\n"
                "data: [DONE]\n\n"
            ),
        )

    payload = suite_payload()
    payload["scenarios"] = [
        {
            "name": "native-stream",
            "mode": "native_stream",
            "requests": 1,
            "concurrency": 1,
        }
    ]
    scenario = parse_suite_config(payload).scenarios[0]

    async def run():
        async with httpx.AsyncClient(
            base_url="http://test",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await execute_request(
                client=client,
                scenario=scenario,
                index=0,
                run_id="run",
                headers={},
            )

    sample = asyncio.run(run())

    assert sample.success is True
    assert sample.status_code == 200
    assert sample.token_events == 2
    assert sample.ttft_ms is not None


def test_execute_request_rejects_stream_without_done():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text="event: token\ndata: partial\n\n",
        )

    payload = suite_payload()
    payload["scenarios"] = [
        {
            "name": "native-stream",
            "mode": "native_stream",
            "requests": 1,
            "concurrency": 1,
        }
    ]
    scenario = parse_suite_config(payload).scenarios[0]

    async def run():
        async with httpx.AsyncClient(
            base_url="http://test",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await execute_request(
                client=client,
                scenario=scenario,
                index=0,
                run_id="run",
                headers={},
            )

    sample = asyncio.run(run())

    assert sample.success is False
    assert sample.error_kind == "missing_terminal_event"


def test_report_contains_metrics_and_never_contains_api_key():
    suite_result = {
        "environment": {
            "captured_at_utc": "2026-08-17T00:00:00+00:00",
            "python": "3.10.19",
            "platform": "Linux",
            "machine": "x86_64",
            "logical_cpu_count": 8,
            "git_commit": "abc123",
            "git_dirty": False,
            "httpx": "0.28.1",
        },
        "config": {
            "suite_name": "unit",
            "base_url": "http://test",
            "api_key_env": "CHAT_API_KEY",
            "api_key_present": True,
            "metadata": {"server_workers": 1},
            "source": "benchmarks/configs/unit.json",
        },
        "results": [
            {
                "scenario": {
                    "name": "sync",
                    "mode": "native_sync",
                    "provider": "mock",
                    "model": "mock-load",
                    "concurrency": 2,
                },
                "summary": {
                    "total_requests": 10,
                    "successful_requests": 9,
                    "failed_requests": 1,
                    "error_rate_percent": 10.0,
                    "throughput_rps": 50.0,
                    "latency_ms": {
                        "p50": 10.0,
                        "p95": 15.0,
                        "p99": 17.0,
                    },
                    "ttft_ms": {
                        "p50": None,
                        "p95": None,
                    },
                    "error_counts": {"http_500": 1},
                    "error_examples": {
                        "http_500": "database is locked"
                    },
                },
            }
        ],
    }

    report = render_markdown_report(suite_result)

    assert "P50 ms" in report
    assert "P95 ms" in report
    assert "50.000" in report
    assert "database is locked" in report
    assert "CHAT_API_KEY" not in report
    assert "secret-value" not in report
