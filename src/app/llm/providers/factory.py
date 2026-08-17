from __future__ import annotations

from typing import Any

from src.app.core.settings import settings

from .base import ChatProvider
from .errors import (
    ProviderConfigurationError,
    UnsupportedProviderError,
)
from .mock import MockProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .resilience import (
    ProviderRetryPolicy,
    ResilientChatProvider,
)


SUPPORTED_CHAT_PROVIDERS = (
    "mock",
    "ollama",
    "openai",
)


def normalize_provider_name(
    provider: str | None,
) -> str:
    return (provider or "mock").strip().lower()


def _get_raw_chat_provider(
    normalized: str,
    *,
    settings_obj: Any,
) -> ChatProvider:
    if normalized == "mock":
        return MockProvider()

    if normalized == "ollama":
        return OllamaProvider(settings_obj=settings_obj)

    if normalized == "openai":
        return OpenAIProvider(settings_obj=settings_obj)

    supported = ", ".join(SUPPORTED_CHAT_PROVIDERS)
    raise UnsupportedProviderError(
        f"Unsupported chat provider: {normalized}. "
        f"Supported providers: {supported}."
    )


def _retry_policy(
    settings_obj: Any,
) -> ProviderRetryPolicy:
    try:
        return ProviderRetryPolicy(
            max_attempts=(
                settings_obj
                .PROVIDER_RETRY_MAX_ATTEMPTS
            ),
            base_delay_ms=(
                settings_obj
                .PROVIDER_RETRY_BASE_DELAY_MS
            ),
            max_delay_ms=(
                settings_obj
                .PROVIDER_RETRY_MAX_DELAY_MS
            ),
        )
    except ValueError as exc:
        raise ProviderConfigurationError(
            "Invalid provider retry configuration: "
            f"{exc}"
        ) from exc


def _get_fallback_provider(
    *,
    primary_name: str,
    settings_obj: Any,
) -> ChatProvider | None:
    if not settings_obj.PROVIDER_FALLBACK_ENABLED:
        return None

    fallback_name = (
        settings_obj
        .PROVIDER_FALLBACK_PROVIDER
        .strip()
        .lower()
    )

    if not fallback_name:
        raise ProviderConfigurationError(
            "PROVIDER_FALLBACK_PROVIDER is required when "
            "PROVIDER_FALLBACK_ENABLED=true."
        )

    # 当客户端直接请求 fallback Provider 时，只应用 retry，
    # 不再构造指向自身的 fallback 环。
    if fallback_name == primary_name:
        return None

    try:
        return _get_raw_chat_provider(
            fallback_name,
            settings_obj=settings_obj,
        )
    except UnsupportedProviderError as exc:
        raise ProviderConfigurationError(
            "Invalid PROVIDER_FALLBACK_PROVIDER: "
            f"{fallback_name}."
        ) from exc


def get_chat_provider(
    provider: str | None,
    *,
    settings_obj: Any = settings,
) -> ChatProvider:
    """构造带统一 retry/fallback 语义的聊天 Provider。"""

    normalized = normalize_provider_name(provider)
    primary = _get_raw_chat_provider(
        normalized,
        settings_obj=settings_obj,
    )
    fallback = _get_fallback_provider(
        primary_name=normalized,
        settings_obj=settings_obj,
    )
    fallback_model = (
        settings_obj
        .PROVIDER_FALLBACK_MODEL
        .strip()
        or None
    )

    return ResilientChatProvider(
        primary=primary,
        retry_policy=_retry_policy(settings_obj),
        fallback=fallback,
        fallback_model=fallback_model,
    )
