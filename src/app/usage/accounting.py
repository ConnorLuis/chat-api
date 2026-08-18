from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.app.conversations import (
    estimate_message_tokens,
    estimate_text_tokens,
)
from src.app.llm.providers import (
    ProviderMessage,
    ProviderUsage,
)


USAGE_SOURCE_PROVIDER_NATIVE = (
    "provider_native"
)
USAGE_SOURCE_LOCAL_ESTIMATE = (
    "local_estimate"
)
USAGE_SOURCE_UNAVAILABLE = (
    "unavailable"
)


@dataclass(
    frozen=True,
    slots=True,
)
class UsageSnapshot:
    usage_source: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


def native_usage_snapshot(
    provider_usage: ProviderUsage | None,
) -> UsageSnapshot | None:
    """只接受完整、非负、内部一致的 Provider usage."""

    if provider_usage is None:
        return None

    values = (
        provider_usage.prompt_tokens,
        provider_usage.completion_tokens,
        provider_usage.total_tokens,
    )

    if any(
        value is None
        for value in values
    ):
        return None

    prompt_tokens = int(
        provider_usage.prompt_tokens
    )
    completion_tokens = int(
        provider_usage.completion_tokens
    )
    total_tokens = int(
        provider_usage.total_tokens
    )

    if min(
        prompt_tokens,
        completion_tokens,
        total_tokens,
    ) < 0:
        return None

    if total_tokens != (
        prompt_tokens
        + completion_tokens
    ):
        return None

    return UsageSnapshot(
        usage_source=(
            USAGE_SOURCE_PROVIDER_NATIVE
        ),
        prompt_tokens=prompt_tokens,
        completion_tokens=(
            completion_tokens
        ),
        total_tokens=total_tokens,
    )


def estimate_usage_snapshot(
    *,
    messages: Sequence[ProviderMessage],
    completion_text: str,
) -> UsageSnapshot:
    """按实际 Provider 输入和当前输出进行本地估算."""

    prompt_tokens = sum(
        estimate_message_tokens(message)
        for message in messages
    )

    completion_tokens = (
        estimate_text_tokens(
            completion_text
        )
        if completion_text
        else 0
    )

    return UsageSnapshot(
        usage_source=(
            USAGE_SOURCE_LOCAL_ESTIMATE
        ),
        prompt_tokens=prompt_tokens,
        completion_tokens=(
            completion_tokens
        ),
        total_tokens=(
            prompt_tokens
            + completion_tokens
        ),
    )


def resolve_usage_snapshot(
    *,
    provider_usage: ProviderUsage | None,
    messages: Sequence[ProviderMessage],
    completion_text: str,
) -> UsageSnapshot:
    """优先使用完整原生 usage，否则统一本地估算."""

    native = native_usage_snapshot(
        provider_usage
    )

    if native is not None:
        return native

    return estimate_usage_snapshot(
        messages=messages,
        completion_text=completion_text,
    )


def unavailable_usage_snapshot() -> UsageSnapshot:
    return UsageSnapshot(
        usage_source=(
            USAGE_SOURCE_UNAVAILABLE
        ),
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
    )


def resolve_terminal_usage_snapshot(
    *,
    provider_usage: ProviderUsage | None,
    messages: Sequence[ProviderMessage],
    completion_text: str,
) -> UsageSnapshot:
    """解析失败或客户端断开时的 usage.

    完整 Provider usage 仍优先作为 provider_native；
    已产生部分输出时可以进行本地估算；
    未获得原生 usage 且没有任何输出时标记 unavailable。
    """

    native = native_usage_snapshot(
        provider_usage
    )

    if native is not None:
        return native

    if completion_text:
        return estimate_usage_snapshot(
            messages=messages,
            completion_text=completion_text,
        )

    return unavailable_usage_snapshot()
