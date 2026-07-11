from __future__ import annotations

from fastapi import Request

from src.app.db.session import (
    SessionFactory,
)
from src.app.services import (
    NewUsageRecord,
)
from src.app.usage import (
    UsageSnapshot,
)
from src.app.usage.persistence import (
    UsagePersistenceResult,
    persist_usage_only,
)


OPENAI_SYNC_REQUEST_KIND = (
    "openai_chat_completions_sync"
)
OPENAI_STREAM_REQUEST_KIND = (
    "openai_chat_completions_stream"
)


def caller_key_id_from_request(
    request: Request,
) -> str | None:
    caller = getattr(
        request.state,
        "caller",
        None,
    )

    if caller is None:
        return None

    return caller.key_id


def persist_openai_usage(
    *,
    session_factory: SessionFactory,
    trace_id: str,
    caller_key_id: str | None,
    request_kind: str,
    provider: str,
    model: str,
    status: str,
    snapshot: UsageSnapshot,
    latency_ms: int,
    error_type: str | None = None,
) -> UsagePersistenceResult:
    return persist_usage_only(
        session_factory=session_factory,
        usage=NewUsageRecord(
            trace_id=trace_id,
            conversation_id=None,
            caller_key_id=caller_key_id,
            request_kind=request_kind,
            provider=provider,
            model=model,
            status=status,
            usage_source=(
                snapshot.usage_source
            ),
            prompt_tokens=(
                snapshot.prompt_tokens
            ),
            completion_tokens=(
                snapshot.completion_tokens
            ),
            total_tokens=(
                snapshot.total_tokens
            ),
            latency_ms=latency_ms,
            error_type=error_type,
        ),
    )
