"""
出现异常时，构建异常信息内容，包含可溯源trace-id、模型引擎、调用模型名、耗时、错误信息。
"""
def build_error(trace_id: str, provider: str, model: str, latency_ms: int, error: str) -> dict:
    return {
        "trace_id": trace_id,
        "provider": provider,
        "model": model if model else "unknown",
        "latency_ms": latency_ms,
        "error": error,
    }