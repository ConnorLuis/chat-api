from __future__ import annotations

from typing import Any

from src.app.core.settings import settings

from .base import ChatProvider
from .errors import UnsupportedProviderError
from .mock import MockProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider


SUPPORTED_CHAT_PROVIDERS = (
    "mock",
    "ollama",
    "openai",
)


def normalize_provider_name(
    provider: str | None,
) -> str:
    return (provider or "mock").strip().lower()


def get_chat_provider(
    provider: str | None,
    *,
    settings_obj: Any = settings,
) -> ChatProvider:
    """根据 provider 名称构造统一聊天 Provider。"""

    normalized = normalize_provider_name(provider)

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
