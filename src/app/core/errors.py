"""
出现异常时，构建异常信息内容，包含可溯源trace-id、模型引擎、调用模型名、耗时、错误信息。
"""
def build_error(
    trace_id: str,
    provider: str,
    model: str,
    latency_ms: int,
    error: str,
    *,
    provider_execution: dict | None = None,
) -> dict:
    payload = {
        "trace_id": trace_id,
        "provider": provider,
        "model": model if model else "unknown",
        "latency_ms": latency_ms,
        "error": error,
    }

    if provider_execution is not None:
        payload[
            "provider_execution"
        ] = provider_execution

    return payload
