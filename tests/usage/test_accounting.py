from src.app.llm.providers import (
    ProviderMessage,
    ProviderUsage,
)
from src.app.usage import (
    USAGE_SOURCE_LOCAL_ESTIMATE,
    USAGE_SOURCE_PROVIDER_NATIVE,
    estimate_usage_snapshot,
    resolve_usage_snapshot,
)


MESSAGES = (
    ProviderMessage(
        role="system",
        content="abcd",
    ),
    ProviderMessage(
        role="user",
        content="hello",
    ),
)


def test_complete_provider_usage_is_native():
    snapshot = resolve_usage_snapshot(
        provider_usage=ProviderUsage(
            prompt_tokens=10,
            completion_tokens=4,
            total_tokens=14,
        ),
        messages=MESSAGES,
        completion_text="ignored",
    )

    assert snapshot.usage_source == (
        USAGE_SOURCE_PROVIDER_NATIVE
    )
    assert snapshot.prompt_tokens == 10
    assert snapshot.completion_tokens == 4
    assert snapshot.total_tokens == 14


def test_incomplete_provider_usage_uses_estimate():
    snapshot = resolve_usage_snapshot(
        provider_usage=ProviderUsage(
            prompt_tokens=10,
            completion_tokens=4,
            total_tokens=None,
        ),
        messages=MESSAGES,
        completion_text="world!",
    )

    assert snapshot.usage_source == (
        USAGE_SOURCE_LOCAL_ESTIMATE
    )
    assert snapshot.prompt_tokens == 13
    assert snapshot.completion_tokens == 3
    assert snapshot.total_tokens == 16


def test_inconsistent_provider_usage_uses_estimate():
    snapshot = resolve_usage_snapshot(
        provider_usage=ProviderUsage(
            prompt_tokens=10,
            completion_tokens=4,
            total_tokens=99,
        ),
        messages=MESSAGES,
        completion_text="world!",
    )

    assert snapshot.usage_source == (
        USAGE_SOURCE_LOCAL_ESTIMATE
    )
    assert snapshot.total_tokens == 16


def test_empty_completion_estimate_is_zero():
    snapshot = estimate_usage_snapshot(
        messages=MESSAGES,
        completion_text="",
    )

    assert snapshot.prompt_tokens == 13
    assert snapshot.completion_tokens == 0
    assert snapshot.total_tokens == 13


def test_terminal_without_usage_or_output_is_unavailable():
    from src.app.usage import (
        USAGE_SOURCE_UNAVAILABLE,
        resolve_terminal_usage_snapshot,
    )

    snapshot = resolve_terminal_usage_snapshot(
        provider_usage=None,
        messages=MESSAGES,
        completion_text="",
    )

    assert snapshot.usage_source == (
        USAGE_SOURCE_UNAVAILABLE
    )
    assert snapshot.prompt_tokens is None
    assert snapshot.completion_tokens is None
    assert snapshot.total_tokens is None


def test_terminal_partial_output_is_estimated():
    from src.app.usage import (
        resolve_terminal_usage_snapshot,
    )

    snapshot = resolve_terminal_usage_snapshot(
        provider_usage=None,
        messages=MESSAGES,
        completion_text="partial",
    )

    assert snapshot.usage_source == (
        USAGE_SOURCE_LOCAL_ESTIMATE
    )
    assert snapshot.prompt_tokens == 13
    assert snapshot.completion_tokens == 4
    assert snapshot.total_tokens == 17
