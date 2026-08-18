import pytest

from src.app.services import (
    ConversationService,
    NewUsageRecord,
    UsageService,
)


def test_record_native_success_usage(
    usage_service: UsageService,
):
    record = usage_service.record_usage(
        NewUsageRecord(
            trace_id="trace-native",
            conversation_id=None,
            request_kind="chat_sync",
            provider="ollama",
            model="qwen2.5:7b",
            status="succeeded",
            usage_source="provider_native",
            prompt_tokens=20,
            completion_tokens=5,
            total_tokens=25,
            latency_ms=100,
        )
    )

    assert record.status == "succeeded"
    assert (
        record.usage_source
        == "provider_native"
    )
    assert record.total_tokens == 25


def test_record_unavailable_failed_usage(
    usage_service: UsageService,
):
    record = usage_service.record_usage(
        NewUsageRecord(
            trace_id="trace-failed",
            conversation_id=None,
            request_kind="chat_stream",
            provider="ollama",
            model="qwen2.5:7b",
            status="provider_failed",
            usage_source="unavailable",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=7,
            error_type="connection_error",
        )
    )

    assert record.status == (
        "provider_failed"
    )
    assert record.total_tokens is None


def test_reject_inconsistent_total_tokens(
    usage_service: UsageService,
):
    with pytest.raises(
        ValueError,
        match="total_tokens must equal",
    ):
        usage_service.record_usage(
            NewUsageRecord(
                trace_id="trace-invalid",
                conversation_id=None,
                request_kind="chat_sync",
                provider="mock",
                model="unknown",
                status="succeeded",
                usage_source="local_estimate",
                prompt_tokens=8,
                completion_tokens=3,
                total_tokens=99,
                latency_ms=1,
            )
        )


def test_usage_survives_conversation_delete(
    conversation_service: ConversationService,
    usage_service: UsageService,
):
    conversation = (
        conversation_service
        .create_conversation(
            title="usage retention",
        )
    )

    record = usage_service.record_usage(
        NewUsageRecord(
            trace_id="trace-retention",
            conversation_id=(
                conversation.id
            ),
            request_kind="chat_sync",
            provider="mock",
            model="unknown",
            status="succeeded",
            usage_source="local_estimate",
            prompt_tokens=8,
            completion_tokens=3,
            total_tokens=11,
            latency_ms=2,
        )
    )

    assert (
        conversation_service
        .delete_conversation(
            conversation.id
        )
        is True
    )

    loaded = usage_service.get_usage_record(
        record.request_id
    )

    assert loaded is not None
    assert loaded.conversation_id == (
        conversation.id
    )
