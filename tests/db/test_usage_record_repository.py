from sqlalchemy.orm import Session

from src.app.db.repositories import (
    UsageRecordRepository,
)


def test_create_and_get_usage_record(
    db_session: Session,
):
    repository = UsageRecordRepository(
        db_session
    )

    created = repository.create(
        trace_id="trace-usage-1",
        conversation_id=None,
        request_kind="chat_sync",
        provider="mock",
        model="mock-model",
        status="succeeded",
        usage_source="local_estimate",
        prompt_tokens=8,
        completion_tokens=3,
        total_tokens=11,
        latency_ms=12,
    )

    db_session.commit()

    loaded = repository.get(
        created.request_id
    )

    assert loaded is not None
    assert loaded.trace_id == "trace-usage-1"
    assert loaded.total_tokens == 11


def test_same_trace_can_have_multiple_records(
    db_session: Session,
):
    repository = UsageRecordRepository(
        db_session
    )

    for provider in ("ollama", "openai"):
        repository.create(
            trace_id="trace-retry",
            conversation_id=None,
            request_kind="chat_sync",
            provider=provider,
            model="model-a",
            status="provider_failed",
            usage_source="unavailable",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=5,
            error_type="provider_error",
        )

    db_session.commit()

    records = repository.list_by_trace(
        "trace-retry"
    )

    assert len(records) == 2
    assert {
        record.provider
        for record in records
    } == {
        "ollama",
        "openai",
    }


def test_create_usage_record_with_caller_key_id(
    db_session: Session,
):
    repository = UsageRecordRepository(
        db_session
    )

    created = repository.create(
        trace_id="trace-caller-usage",
        conversation_id=None,
        caller_key_id="key-day10-caller",
        request_kind="chat_sync",
        provider="mock",
        model="mock-model",
        status="succeeded",
        usage_source="local_estimate",
        prompt_tokens=5,
        completion_tokens=2,
        total_tokens=7,
        latency_ms=3,
    )

    db_session.commit()

    loaded = repository.get(
        created.request_id
    )

    assert loaded is not None
    assert (
        loaded.caller_key_id
        == "key-day10-caller"
    )
