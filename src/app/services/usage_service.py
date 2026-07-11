from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.app.db.models import UsageRecord
from src.app.db.repositories import (
    UsageRecordRepository,
)
from src.app.usage import (
    USAGE_SOURCE_LOCAL_ESTIMATE,
    USAGE_SOURCE_PROVIDER_NATIVE,
    USAGE_SOURCE_UNAVAILABLE,
)


USAGE_STATUS_SUCCEEDED = "succeeded"
USAGE_STATUS_PROVIDER_FAILED = (
    "provider_failed"
)
USAGE_STATUS_CLIENT_DISCONNECTED = (
    "client_disconnected"
)
USAGE_STATUS_PERSISTENCE_FAILED = (
    "persistence_failed"
)

ALLOWED_USAGE_STATUSES = frozenset({
    USAGE_STATUS_SUCCEEDED,
    USAGE_STATUS_PROVIDER_FAILED,
    USAGE_STATUS_CLIENT_DISCONNECTED,
    USAGE_STATUS_PERSISTENCE_FAILED,
})

ALLOWED_USAGE_SOURCES = frozenset({
    USAGE_SOURCE_PROVIDER_NATIVE,
    USAGE_SOURCE_LOCAL_ESTIMATE,
    USAGE_SOURCE_UNAVAILABLE,
})


@dataclass(
    frozen=True,
    slots=True,
)
class NewUsageRecord:
    trace_id: str
    conversation_id: str | None
    request_kind: str
    provider: str
    model: str
    status: str
    usage_source: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    error_type: str | None = None
    caller_key_id: str | None = None


class UsageService:
    """请求级 token accounting 持久化边界."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session
        self.records = (
            UsageRecordRepository(session)
        )

    @staticmethod
    def _required_text(
        value: str,
        *,
        field_name: str,
        max_length: int,
        lower: bool = False,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{field_name} must not be empty"
            )

        if lower:
            normalized = normalized.lower()

        if len(normalized) > max_length:
            raise ValueError(
                f"{field_name} must contain at most "
                f"{max_length} characters"
            )

        return normalized

    @staticmethod
    def _optional_text(
        value: str | None,
        *,
        field_name: str,
        max_length: int,
        lower: bool = False,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            return None

        if lower:
            normalized = normalized.lower()

        if len(normalized) > max_length:
            raise ValueError(
                f"{field_name} must contain at most "
                f"{max_length} characters"
            )

        return normalized

    @classmethod
    def _normalize(
        cls,
        item: NewUsageRecord,
    ) -> NewUsageRecord:
        trace_id = cls._required_text(
            item.trace_id,
            field_name="trace_id",
            max_length=100,
        )
        conversation_id = cls._optional_text(
            item.conversation_id,
            field_name="conversation_id",
            max_length=36,
        )
        caller_key_id = cls._optional_text(
            item.caller_key_id,
            field_name="caller_key_id",
            max_length=36,
        )
        request_kind = cls._required_text(
            item.request_kind,
            field_name="request_kind",
            max_length=50,
            lower=True,
        )
        provider = cls._required_text(
            item.provider,
            field_name="provider",
            max_length=50,
            lower=True,
        )
        model = cls._required_text(
            item.model,
            field_name="model",
            max_length=200,
        )
        status = cls._required_text(
            item.status,
            field_name="status",
            max_length=32,
            lower=True,
        )
        usage_source = cls._required_text(
            item.usage_source,
            field_name="usage_source",
            max_length=32,
            lower=True,
        )
        error_type = cls._optional_text(
            item.error_type,
            field_name="error_type",
            max_length=100,
            lower=True,
        )

        if status not in ALLOWED_USAGE_STATUSES:
            raise ValueError(
                f"Unsupported usage status: {status}"
            )

        if usage_source not in ALLOWED_USAGE_SOURCES:
            raise ValueError(
                "Unsupported usage source: "
                f"{usage_source}"
            )

        if item.latency_ms < 0:
            raise ValueError(
                "latency_ms must be greater than "
                "or equal to 0"
            )

        tokens = (
            item.prompt_tokens,
            item.completion_tokens,
            item.total_tokens,
        )

        if usage_source == USAGE_SOURCE_UNAVAILABLE:
            if any(
                value is not None
                for value in tokens
            ):
                raise ValueError(
                    "unavailable usage must not "
                    "contain token values"
                )

            if status == USAGE_STATUS_SUCCEEDED:
                raise ValueError(
                    "succeeded usage cannot be "
                    "unavailable"
                )

        else:
            if any(
                value is None
                for value in tokens
            ):
                raise ValueError(
                    "native or estimated usage must "
                    "contain all token values"
                )

            prompt_tokens = int(
                item.prompt_tokens
            )
            completion_tokens = int(
                item.completion_tokens
            )
            total_tokens = int(
                item.total_tokens
            )

            if min(
                prompt_tokens,
                completion_tokens,
                total_tokens,
            ) < 0:
                raise ValueError(
                    "token values must be greater "
                    "than or equal to 0"
                )

            if total_tokens != (
                prompt_tokens
                + completion_tokens
            ):
                raise ValueError(
                    "total_tokens must equal "
                    "prompt_tokens + "
                    "completion_tokens"
                )

        return NewUsageRecord(
            trace_id=trace_id,
            conversation_id=conversation_id,
            request_kind=request_kind,
            caller_key_id=caller_key_id,
            provider=provider,
            model=model,
            status=status,
            usage_source=usage_source,
            prompt_tokens=item.prompt_tokens,
            completion_tokens=(
                item.completion_tokens
            ),
            total_tokens=item.total_tokens,
            latency_ms=item.latency_ms,
            error_type=error_type,
        )

    def record_usage(
        self,
        item: NewUsageRecord,
        *,
        commit: bool = True,
    ) -> UsageRecord:
        normalized = self._normalize(item)

        try:
            record = self.records.create(
                trace_id=normalized.trace_id,
                conversation_id=(
                    normalized.conversation_id
                ),
                caller_key_id=(
                    normalized.caller_key_id
                ),
                request_kind=(
                    normalized.request_kind
                ),
                provider=normalized.provider,
                model=normalized.model,
                status=normalized.status,
                usage_source=(
                    normalized.usage_source
                ),
                prompt_tokens=(
                    normalized.prompt_tokens
                ),
                completion_tokens=(
                    normalized.completion_tokens
                ),
                total_tokens=(
                    normalized.total_tokens
                ),
                latency_ms=(
                    normalized.latency_ms
                ),
                error_type=(
                    normalized.error_type
                ),
            )

            if commit:
                self.session.commit()
                self.session.refresh(record)

            else:
                self.session.flush()

            return record

        except Exception:
            self.session.rollback()
            raise

    def get_usage_record(
        self,
        request_id: str,
    ) -> UsageRecord | None:
        return self.records.get(
            request_id
        )

    def list_by_trace(
        self,
        trace_id: str,
    ) -> list[UsageRecord]:
        return self.records.list_by_trace(
            trace_id
        )
