from __future__ import annotations

import asyncio
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import httpx


SUPPORTED_MODES = frozenset(
    {
        "native_sync",
        "native_stream",
        "openai_sync",
        "openai_stream",
    }
)
STREAM_MODES = frozenset(
    {"native_stream", "openai_stream"}
)
SCENARIO_FIELDS = frozenset(
    {
        "name",
        "mode",
        "provider",
        "model",
        "requests",
        "concurrency",
        "warmup_requests",
        "prompt",
        "max_tokens",
        "timeout_s",
    }
)
SUITE_FIELDS = frozenset(
    {
        "suite_name",
        "base_url",
        "api_key_env",
        "metadata",
        "defaults",
        "scenarios",
    }
)


class LoadTestConfigError(ValueError):
    """Raised when a load-test suite is not reproducible or valid."""


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    name: str
    mode: str
    provider: str
    model: str | None
    requests: int
    concurrency: int
    warmup_requests: int
    prompt: str
    max_tokens: int
    timeout_s: float

    @property
    def is_streaming(self) -> bool:
        return self.mode in STREAM_MODES


@dataclass(frozen=True, slots=True)
class SuiteConfig:
    suite_name: str
    base_url: str
    api_key_env: str
    metadata: dict[str, Any]
    scenarios: tuple[ScenarioConfig, ...]


@dataclass(slots=True)
class RequestSample:
    index: int
    trace_id: str
    success: bool
    status_code: int | None
    latency_ms: float
    ttft_ms: float | None
    response_bytes: int
    token_events: int
    error_kind: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _non_empty_string(
    value: Any,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LoadTestConfigError(
            f"{field} must be a non-empty string"
        )
    return value.strip()


def _integer(
    value: Any,
    *,
    field: str,
    minimum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LoadTestConfigError(
            f"{field} must be an integer"
        )
    if value < minimum:
        raise LoadTestConfigError(
            f"{field} must be >= {minimum}"
        )
    return value


def _positive_number(
    value: Any,
    *,
    field: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0
    ):
        raise LoadTestConfigError(
            f"{field} must be a finite number > 0"
        )
    return float(value)


def _reject_unknown_fields(
    payload: Mapping[str, Any],
    *,
    allowed: frozenset[str],
    context: str,
) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise LoadTestConfigError(
            f"{context} has unknown fields: "
            + ", ".join(unknown)
        )


def parse_suite_config(
    payload: Mapping[str, Any],
) -> SuiteConfig:
    """Validate a JSON-compatible suite mapping."""

    if not isinstance(payload, Mapping):
        raise LoadTestConfigError(
            "suite config must be a JSON object"
        )
    _reject_unknown_fields(
        payload,
        allowed=SUITE_FIELDS,
        context="suite config",
    )

    suite_name = _non_empty_string(
        payload.get("suite_name"),
        field="suite_name",
    )
    base_url = _non_empty_string(
        payload.get(
            "base_url",
            "http://127.0.0.1:8000",
        ),
        field="base_url",
    ).rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise LoadTestConfigError(
            "base_url must start with http:// or https://"
        )

    api_key_env = _non_empty_string(
        payload.get("api_key_env", "CHAT_API_KEY"),
        field="api_key_env",
    )

    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise LoadTestConfigError(
            "metadata must be a JSON object"
        )
    try:
        json.dumps(metadata)
    except (TypeError, ValueError) as exc:
        raise LoadTestConfigError(
            "metadata must be JSON-serializable"
        ) from exc

    defaults = payload.get("defaults", {})
    if not isinstance(defaults, Mapping):
        raise LoadTestConfigError(
            "defaults must be a JSON object"
        )
    _reject_unknown_fields(
        defaults,
        allowed=SCENARIO_FIELDS - {"name"},
        context="defaults",
    )

    raw_scenarios = payload.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise LoadTestConfigError(
            "scenarios must be a non-empty JSON array"
        )

    names: set[str] = set()
    scenarios: list[ScenarioConfig] = []
    for index, raw_scenario in enumerate(raw_scenarios):
        if not isinstance(raw_scenario, Mapping):
            raise LoadTestConfigError(
                f"scenarios[{index}] must be a JSON object"
            )
        _reject_unknown_fields(
            raw_scenario,
            allowed=SCENARIO_FIELDS,
            context=f"scenarios[{index}]",
        )
        merged = {**defaults, **raw_scenario}
        name = _non_empty_string(
            merged.get("name"),
            field=f"scenarios[{index}].name",
        )
        if name in names:
            raise LoadTestConfigError(
                f"scenario name must be unique: {name}"
            )
        names.add(name)

        mode = _non_empty_string(
            merged.get("mode"),
            field=f"scenarios[{index}].mode",
        ).lower()
        if mode not in SUPPORTED_MODES:
            choices = ", ".join(sorted(SUPPORTED_MODES))
            raise LoadTestConfigError(
                f"unsupported mode {mode!r}; expected one of: "
                f"{choices}"
            )

        provider = _non_empty_string(
            merged.get("provider", "mock"),
            field=f"scenarios[{index}].provider",
        ).lower()

        raw_model = merged.get("model")
        model = None
        if raw_model is not None:
            model = _non_empty_string(
                raw_model,
                field=f"scenarios[{index}].model",
            )
        if mode.startswith("openai_") and model is None:
            raise LoadTestConfigError(
                f"scenario {name!r} requires model for "
                "OpenAI-compatible requests"
            )

        requests = _integer(
            merged.get("requests"),
            field=f"scenarios[{index}].requests",
            minimum=1,
        )
        concurrency = _integer(
            merged.get("concurrency"),
            field=f"scenarios[{index}].concurrency",
            minimum=1,
        )
        if concurrency > requests:
            raise LoadTestConfigError(
                f"scenario {name!r} concurrency cannot exceed "
                "requests"
            )

        warmup_requests = _integer(
            merged.get("warmup_requests", 3),
            field=f"scenarios[{index}].warmup_requests",
            minimum=0,
        )
        prompt = _non_empty_string(
            merged.get("prompt", "Reply with OK."),
            field=f"scenarios[{index}].prompt",
        )
        max_tokens = _integer(
            merged.get("max_tokens", 32),
            field=f"scenarios[{index}].max_tokens",
            minimum=1,
        )
        timeout_s = _positive_number(
            merged.get("timeout_s", 30),
            field=f"scenarios[{index}].timeout_s",
        )

        scenarios.append(
            ScenarioConfig(
                name=name,
                mode=mode,
                provider=provider,
                model=model,
                requests=requests,
                concurrency=concurrency,
                warmup_requests=warmup_requests,
                prompt=prompt,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
            )
        )

    return SuiteConfig(
        suite_name=suite_name,
        base_url=base_url,
        api_key_env=api_key_env,
        metadata=dict(metadata),
        scenarios=tuple(scenarios),
    )


def load_suite_config(path: Path) -> SuiteConfig:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LoadTestConfigError(
            f"config file not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise LoadTestConfigError(
            f"invalid JSON in {path}: {exc}"
        ) from exc
    return parse_suite_config(payload)


def percentile(
    values: Sequence[float],
    quantile: float,
) -> float | None:
    """Return a linearly interpolated percentile over sorted samples."""

    if not values:
        return None
    if quantile < 0 or quantile > 1:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * quantile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return (
        ordered[lower] * (1 - weight)
        + ordered[upper] * weight
    )


def _rounded(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 3)


def metric_summary(
    values: Sequence[float],
) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "mean": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "max": None,
        }
    return {
        "count": len(values),
        "min": _rounded(min(values)),
        "mean": _rounded(statistics.fmean(values)),
        "p50": _rounded(percentile(values, 0.50)),
        "p95": _rounded(percentile(values, 0.95)),
        "p99": _rounded(percentile(values, 0.99)),
        "max": _rounded(max(values)),
    }


def summarize_samples(
    samples: Sequence[RequestSample],
    *,
    wall_seconds: float,
) -> dict[str, Any]:
    total = len(samples)
    succeeded = sum(sample.success for sample in samples)
    failed = total - succeeded
    status_counts = Counter(
        str(sample.status_code)
        if sample.status_code is not None
        else "transport_error"
        for sample in samples
    )
    error_counts = Counter(
        sample.error_kind
        for sample in samples
        if sample.error_kind is not None
    )
    error_examples: dict[str, str] = {}
    for sample in samples:
        if (
            sample.error_kind is not None
            and sample.error_message
            and sample.error_kind not in error_examples
        ):
            error_examples[sample.error_kind] = _truncate(
                sample.error_message,
                limit=240,
            )
    latencies = [sample.latency_ms for sample in samples]
    ttfts = [
        sample.ttft_ms
        for sample in samples
        if sample.ttft_ms is not None
    ]
    error_rate = failed / total if total else 0.0
    throughput = total / wall_seconds if wall_seconds > 0 else 0.0

    return {
        "total_requests": total,
        "successful_requests": succeeded,
        "failed_requests": failed,
        "error_rate": round(error_rate, 6),
        "error_rate_percent": round(error_rate * 100, 3),
        "wall_seconds": round(wall_seconds, 6),
        "throughput_rps": round(throughput, 3),
        "latency_ms": metric_summary(latencies),
        "ttft_ms": metric_summary(ttfts),
        "status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(sorted(error_counts.items())),
        "error_examples": dict(sorted(error_examples.items())),
        "response_bytes": sum(
            sample.response_bytes for sample in samples
        ),
        "token_events": sum(
            sample.token_events for sample in samples
        ),
    }


def build_request_payload(
    scenario: ScenarioConfig,
) -> tuple[str, dict[str, Any]]:
    messages = [
        {
            "role": "user",
            "content": scenario.prompt,
        }
    ]
    if scenario.mode.startswith("native_"):
        payload: dict[str, Any] = {
            "provider": scenario.provider,
            "messages": messages,
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": scenario.max_tokens,
            "use_kb": False,
        }
        if scenario.model is not None:
            payload["model"] = scenario.model
        path = (
            "/chat/stream"
            if scenario.is_streaming
            else "/chat"
        )
        return path, payload

    payload = {
        "provider": scenario.provider,
        "model": scenario.model,
        "messages": messages,
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": scenario.max_tokens,
        "stream": scenario.is_streaming,
    }
    if scenario.is_streaming:
        payload["stream_options"] = {
            "include_usage": True,
        }
    return "/v1/chat/completions", payload


def parse_sse_block(
    lines: Sequence[str],
) -> tuple[str | None, str]:
    event: str | None = None
    data_lines: list[str] = []
    for line in lines:
        if line.startswith(":"):
            continue
        field, separator, raw_value = line.partition(":")
        value = raw_value
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            event = value
        elif field == "data":
            data_lines.append(value)
    return event, "\n".join(data_lines)


def native_sse_outcome(
    event: str | None,
    data: str,
) -> tuple[str | None, bool, str | None]:
    if event == "token":
        return data, False, None
    if event == "done" and data == "[DONE]":
        return None, True, None
    if event == "error":
        return None, False, data or "native SSE error event"
    return None, False, None


def openai_sse_outcome(
    data: str,
) -> tuple[str | None, bool, str | None]:
    if data == "[DONE]":
        return None, True, None
    if not data:
        return None, False, None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None, False, "invalid OpenAI-compatible SSE JSON"
    if not isinstance(payload, dict):
        return None, False, "unexpected OpenAI-compatible SSE payload"
    if "error" in payload:
        return None, False, json.dumps(
            payload["error"],
            ensure_ascii=False,
        )

    parts: list[str] = []
    choices = payload.get("choices", [])
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            content = delta.get("content")
            if isinstance(content, str) and content != "":
                parts.append(content)
    token = "".join(parts) if parts else None
    return token, False, None


def _truncate(value: str, limit: int = 500) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _response_error(response: httpx.Response) -> str:
    try:
        return _truncate(
            json.dumps(
                response.json(),
                ensure_ascii=False,
            )
        )
    except (ValueError, TypeError):
        return _truncate(response.text)


def _sample(
    *,
    index: int,
    trace_id: str,
    started_at: float,
    success: bool,
    status_code: int | None,
    response_bytes: int,
    token_events: int,
    ttft_ms: float | None = None,
    error_kind: str | None = None,
    error_message: str | None = None,
) -> RequestSample:
    return RequestSample(
        index=index,
        trace_id=trace_id,
        success=success,
        status_code=status_code,
        latency_ms=round(
            (time.perf_counter() - started_at) * 1000,
            3,
        ),
        ttft_ms=_rounded(ttft_ms),
        response_bytes=response_bytes,
        token_events=token_events,
        error_kind=error_kind,
        error_message=(
            _truncate(error_message)
            if error_message
            else None
        ),
    )


async def _execute_sync_request(
    *,
    client: httpx.AsyncClient,
    scenario: ScenarioConfig,
    index: int,
    trace_id: str,
    headers: Mapping[str, str],
) -> RequestSample:
    path, payload = build_request_payload(scenario)
    started_at = time.perf_counter()
    response = await client.post(
        path,
        json=payload,
        headers={**headers, "x-trace-id": trace_id},
    )
    response_bytes = len(response.content)
    if not 200 <= response.status_code < 300:
        return _sample(
            index=index,
            trace_id=trace_id,
            started_at=started_at,
            success=False,
            status_code=response.status_code,
            response_bytes=response_bytes,
            token_events=0,
            error_kind=f"http_{response.status_code}",
            error_message=_response_error(response),
        )

    try:
        body = response.json()
    except ValueError as exc:
        return _sample(
            index=index,
            trace_id=trace_id,
            started_at=started_at,
            success=False,
            status_code=response.status_code,
            response_bytes=response_bytes,
            token_events=0,
            error_kind="invalid_json",
            error_message=str(exc),
        )

    valid = False
    if scenario.mode == "native_sync":
        valid = (
            isinstance(body, dict)
            and isinstance(body.get("answer"), str)
            and isinstance(body.get("trace_id"), str)
        )
    elif scenario.mode == "openai_sync":
        valid = (
            isinstance(body, dict)
            and body.get("object") == "chat.completion"
            and isinstance(body.get("choices"), list)
            and bool(body["choices"])
        )

    if not valid:
        return _sample(
            index=index,
            trace_id=trace_id,
            started_at=started_at,
            success=False,
            status_code=response.status_code,
            response_bytes=response_bytes,
            token_events=0,
            error_kind="response_contract",
            error_message="HTTP 2xx response did not match the expected contract",
        )

    return _sample(
        index=index,
        trace_id=trace_id,
        started_at=started_at,
        success=True,
        status_code=response.status_code,
        response_bytes=response_bytes,
        token_events=0,
    )


async def _execute_stream_request(
    *,
    client: httpx.AsyncClient,
    scenario: ScenarioConfig,
    index: int,
    trace_id: str,
    headers: Mapping[str, str],
) -> RequestSample:
    path, payload = build_request_payload(scenario)
    started_at = time.perf_counter()
    response_bytes = 0
    token_events = 0
    ttft_ms: float | None = None
    terminal_seen = False
    semantic_error: str | None = None

    async with client.stream(
        "POST",
        path,
        json=payload,
        headers={**headers, "x-trace-id": trace_id},
    ) as response:
        if not 200 <= response.status_code < 300:
            content = await response.aread()
            response_bytes = len(content)
            return _sample(
                index=index,
                trace_id=trace_id,
                started_at=started_at,
                success=False,
                status_code=response.status_code,
                response_bytes=response_bytes,
                token_events=0,
                error_kind=f"http_{response.status_code}",
                error_message=_truncate(
                    content.decode("utf-8", errors="replace")
                ),
            )

        block: list[str] = []

        def consume_block(lines: Sequence[str]) -> None:
            nonlocal token_events
            nonlocal ttft_ms
            nonlocal terminal_seen
            nonlocal semantic_error

            event, data = parse_sse_block(lines)
            if scenario.mode == "native_stream":
                token, done, error = native_sse_outcome(
                    event,
                    data,
                )
            else:
                token, done, error = openai_sse_outcome(data)
            if token is not None:
                token_events += 1
                if ttft_ms is None:
                    ttft_ms = (
                        time.perf_counter() - started_at
                    ) * 1000
            if done:
                terminal_seen = True
            if error is not None and semantic_error is None:
                semantic_error = error

        async for line in response.aiter_lines():
            response_bytes += len(line.encode("utf-8")) + 1
            if line == "":
                if block:
                    consume_block(block)
                    block = []
                continue
            block.append(line)
        if block:
            consume_block(block)

        if semantic_error is not None:
            return _sample(
                index=index,
                trace_id=trace_id,
                started_at=started_at,
                success=False,
                status_code=response.status_code,
                response_bytes=response_bytes,
                token_events=token_events,
                ttft_ms=ttft_ms,
                error_kind="stream_error",
                error_message=semantic_error,
            )
        if not terminal_seen:
            return _sample(
                index=index,
                trace_id=trace_id,
                started_at=started_at,
                success=False,
                status_code=response.status_code,
                response_bytes=response_bytes,
                token_events=token_events,
                ttft_ms=ttft_ms,
                error_kind="missing_terminal_event",
                error_message=(
                    "stream ended without native done or OpenAI [DONE]"
                ),
            )
        return _sample(
            index=index,
            trace_id=trace_id,
            started_at=started_at,
            success=True,
            status_code=response.status_code,
            response_bytes=response_bytes,
            token_events=token_events,
            ttft_ms=ttft_ms,
        )


async def execute_request(
    *,
    client: httpx.AsyncClient,
    scenario: ScenarioConfig,
    index: int,
    run_id: str,
    headers: Mapping[str, str],
) -> RequestSample:
    trace_id = (
        f"load-{run_id}-{scenario.name}-{index}-"
        f"{uuid.uuid4().hex[:8]}"
    )
    started_at = time.perf_counter()
    try:
        if scenario.is_streaming:
            return await _execute_stream_request(
                client=client,
                scenario=scenario,
                index=index,
                trace_id=trace_id,
                headers=headers,
            )
        return await _execute_sync_request(
            client=client,
            scenario=scenario,
            index=index,
            trace_id=trace_id,
            headers=headers,
        )
    except httpx.TimeoutException as exc:
        error_kind = "timeout"
        error_message = str(exc) or type(exc).__name__
    except httpx.ConnectError as exc:
        error_kind = "transport_connect"
        error_message = str(exc) or type(exc).__name__
    except httpx.TransportError as exc:
        error_kind = f"transport_{type(exc).__name__.lower()}"
        error_message = str(exc) or type(exc).__name__
    except Exception as exc:  # benchmark must count unexpected client failures
        error_kind = f"client_{type(exc).__name__.lower()}"
        error_message = str(exc) or type(exc).__name__
    return _sample(
        index=index,
        trace_id=trace_id,
        started_at=started_at,
        success=False,
        status_code=None,
        response_bytes=0,
        token_events=0,
        error_kind=error_kind,
        error_message=error_message,
    )


async def _check_server(
    *,
    base_url: str,
    headers: Mapping[str, str],
) -> None:
    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        trust_env=False,
    ) as client:
        for path in ("/health", "/ready"):
            try:
                response = await client.get(path, headers=headers)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise RuntimeError(
                    f"server preflight failed for {base_url}{path}: {exc}"
                ) from exc


async def run_scenario(
    *,
    suite: SuiteConfig,
    scenario: ScenarioConfig,
    run_id: str,
    headers: Mapping[str, str],
) -> tuple[dict[str, Any], list[RequestSample]]:
    limits = httpx.Limits(
        max_connections=scenario.concurrency,
        max_keepalive_connections=scenario.concurrency,
    )
    timeout = httpx.Timeout(scenario.timeout_s)
    async with httpx.AsyncClient(
        base_url=suite.base_url,
        limits=limits,
        timeout=timeout,
        trust_env=False,
    ) as client:
        for index in range(scenario.warmup_requests):
            warmup = await execute_request(
                client=client,
                scenario=scenario,
                index=-(index + 1),
                run_id=run_id,
                headers=headers,
            )
            if not warmup.success:
                raise RuntimeError(
                    f"warmup failed for {scenario.name}: "
                    f"{warmup.error_kind}: {warmup.error_message}"
                )

        queue: asyncio.Queue[int] = asyncio.Queue()
        for index in range(scenario.requests):
            queue.put_nowait(index)
        samples: list[RequestSample | None] = [
            None
        ] * scenario.requests

        async def worker() -> None:
            while True:
                try:
                    index = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    samples[index] = await execute_request(
                        client=client,
                        scenario=scenario,
                        index=index,
                        run_id=run_id,
                        headers=headers,
                    )
                finally:
                    queue.task_done()

        started_at = time.perf_counter()
        await asyncio.gather(
            *(
                worker()
                for _ in range(scenario.concurrency)
            )
        )
        wall_seconds = time.perf_counter() - started_at

    completed = [
        sample for sample in samples if sample is not None
    ]
    if len(completed) != scenario.requests:
        raise RuntimeError(
            f"scenario {scenario.name} lost request samples"
        )
    summary = summarize_samples(
        completed,
        wall_seconds=wall_seconds,
    )
    return summary, completed


def _git_output(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ):
        return None
    return result.stdout.strip()


def environment_snapshot() -> dict[str, Any]:
    dirty_output = _git_output("status", "--porcelain")
    return {
        "captured_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
        "git_commit": _git_output("rev-parse", "HEAD"),
        "git_dirty": (
            bool(dirty_output)
            if dirty_output is not None
            else None
        ),
        "httpx": httpx.__version__,
    }


def _safe_name(value: str) -> str:
    normalized = "".join(
        character
        if (
            character.isascii()
            and (
                character.isalnum()
                or character in {"-", "_"}
            )
        )
        else "-"
        for character in value
    ).strip("-")
    return normalized or "load-test"


def _format_metric(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown_report(
    suite_result: Mapping[str, Any],
) -> str:
    environment = suite_result["environment"]
    config = suite_result["config"]
    results = suite_result["results"]
    lines = [
        f"# Load-test report: {config['suite_name']}",
        "",
        "> Generated by `scripts/run_load_test.py`. "
        "Results describe this exact environment and are not a "
        "universal capacity claim.",
        "",
        "## Summary",
        "",
        "| Scenario | Mode | Provider | Model | C | Requests | Success | Error rate | RPS | P50 ms | P95 ms | P99 ms | TTFT P50 ms | TTFT P95 ms |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        scenario = result["scenario"]
        summary = result["summary"]
        latency = summary["latency_ms"]
        ttft = summary["ttft_ms"]
        lines.append(
            "| "
            + " | ".join(
                _escape_table(value)
                for value in (
                    scenario["name"],
                    scenario["mode"],
                    scenario["provider"],
                    scenario["model"] or "default",
                    scenario["concurrency"],
                    summary["total_requests"],
                    summary["successful_requests"],
                    f"{summary['error_rate_percent']:.3f}%",
                    _format_metric(summary["throughput_rps"]),
                    _format_metric(latency["p50"]),
                    _format_metric(latency["p95"]),
                    _format_metric(latency["p99"]),
                    _format_metric(ttft["p50"]),
                    _format_metric(ttft["p95"]),
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Measurement contract",
            "",
            "- Warm-up requests are excluded from all measurements.",
            "- Throughput is completed measured requests divided by the scenario wall-clock window.",
            "- Latency is measured from immediately before the HTTP request until the full response body or stream is consumed.",
            "- P50/P95/P99 use linear interpolation over all measured request latencies.",
            "- Streaming TTFT is time to the first non-empty native `token` event or OpenAI-compatible content delta.",
            "- Success requires HTTP 2xx plus the expected JSON contract or terminal SSE event; semantic stream errors and missing terminal events count as failures.",
            "",
            "## Environment",
            "",
            f"- Captured (UTC): `{environment.get('captured_at_utc')}`",
            f"- Base URL: `{config['base_url']}`",
            f"- Git commit: `{environment.get('git_commit') or 'unknown'}`",
            f"- Git dirty: `{environment.get('git_dirty')}`",
            f"- Python: `{environment.get('python')}`",
            f"- Platform: `{environment.get('platform')}`",
            f"- Machine: `{environment.get('machine')}`",
            f"- Logical CPUs: `{environment.get('logical_cpu_count')}`",
            f"- httpx: `{environment.get('httpx')}`",
        ]
    )
    metadata = config.get("metadata", {})
    if metadata:
        lines.extend(["", "### Declared run metadata", ""])
        for key, value in sorted(metadata.items()):
            lines.append(
                f"- {_escape_table(key)}: `{_escape_table(value)}`"
            )

    failures = [
        result
        for result in results
        if result["summary"]["failed_requests"] > 0
    ]
    lines.extend(["", "## Errors", ""])
    if not failures:
        lines.append("No measured request failures.")
    else:
        lines.extend(
            [
                "| Scenario | Error kind | Count | Representative error |",
                "|---|---|---:|---|",
            ]
        )
        for result in failures:
            for error_kind, count in result["summary"][
                "error_counts"
            ].items():
                lines.append(
                    f"| {_escape_table(result['scenario']['name'])} "
                    f"| {_escape_table(error_kind)} | {count} "
                    f"| {_escape_table(result['summary'].get('error_examples', {}).get(error_kind, '—'))} |"
                )

    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "Run the same committed config against a server started with the same worker count and feature flags:",
            "",
            "```bash",
            f"python scripts/run_load_test.py --config {config.get('source', '<config.json>')}",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


async def run_suite(
    *,
    suite: SuiteConfig,
    config_source: str,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    api_key = os.getenv(suite.api_key_env, "").strip()
    headers = {
        "user-agent": "chat-api-day12-load-test/1.0",
    }
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    await _check_server(
        base_url=suite.base_url,
        headers=headers,
    )
    environment = environment_snapshot()
    config_payload = {
        "suite_name": suite.suite_name,
        "base_url": suite.base_url,
        "api_key_env": suite.api_key_env,
        "api_key_present": bool(api_key),
        "metadata": suite.metadata,
        "source": config_source,
        "scenarios": [
            asdict(scenario) for scenario in suite.scenarios
        ],
    }
    results: list[dict[str, Any]] = []

    for scenario in suite.scenarios:
        print(
            f"[run] {scenario.name}: mode={scenario.mode} "
            f"requests={scenario.requests} "
            f"concurrency={scenario.concurrency}",
            flush=True,
        )
        summary, samples = await run_scenario(
            suite=suite,
            scenario=scenario,
            run_id=run_id,
            headers=headers,
        )
        result_file = f"{_safe_name(scenario.name)}.json"
        scenario_result = {
            "run_id": run_id,
            "environment": environment,
            "scenario": asdict(scenario),
            "summary": summary,
            "samples": [sample.to_dict() for sample in samples],
        }
        _write_json(output_dir / result_file, scenario_result)
        results.append(
            {
                "scenario": asdict(scenario),
                "summary": summary,
                "result_file": result_file,
            }
        )
        print(
            f"[done] {scenario.name}: "
            f"rps={summary['throughput_rps']:.3f} "
            f"p50={summary['latency_ms']['p50']}ms "
            f"p95={summary['latency_ms']['p95']}ms "
            f"errors={summary['error_rate_percent']:.3f}%",
            flush=True,
        )

    suite_result = {
        "schema_version": 1,
        "run_id": run_id,
        "environment": environment,
        "config": config_payload,
        "results": results,
    }
    _write_json(output_dir / "summary.json", suite_result)
    (output_dir / "report.md").write_text(
        render_markdown_report(suite_result),
        encoding="utf-8",
    )
    return suite_result


def default_output_dir(suite_name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    return (
        Path("benchmarks")
        / "results"
        / f"{_safe_name(suite_name)}-{timestamp}"
    )
