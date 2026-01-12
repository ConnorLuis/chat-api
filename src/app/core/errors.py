def build_error(trace_id: str, provider: str, model: str, latency_ms: int, error: str) -> dict:
    return {
        "trace_id": trace_id,
        "provider": provider,
        "model": model if model else "unknown",
        "latency_ms": latency_ms,
        "error": error,
    }