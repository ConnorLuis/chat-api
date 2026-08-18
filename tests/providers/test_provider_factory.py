import pytest

from src.app.llm.providers import (
    MockProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderConfigurationError,
    ResilientChatProvider,
    UnsupportedProviderError,
    get_chat_provider,
)


def clear_resilience_environment(monkeypatch):
    for key in (
        "PROVIDER_RETRY_MAX_ATTEMPTS",
        "PROVIDER_RETRY_BASE_DELAY_MS",
        "PROVIDER_RETRY_MAX_DELAY_MS",
        "PROVIDER_FALLBACK_ENABLED",
        "PROVIDER_FALLBACK_PROVIDER",
        "PROVIDER_FALLBACK_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_provider_factory_wraps_mock_provider(monkeypatch):
    clear_resilience_environment(monkeypatch)

    provider = get_chat_provider("mock")

    assert isinstance(provider, ResilientChatProvider)
    assert isinstance(provider.primary, MockProvider)
    assert provider.name == "mock"


def test_provider_factory_wraps_ollama_provider(monkeypatch):
    clear_resilience_environment(monkeypatch)

    provider = get_chat_provider("ollama")

    assert isinstance(provider, ResilientChatProvider)
    assert isinstance(provider.primary, OllamaProvider)


def test_provider_factory_wraps_openai_provider(monkeypatch):
    clear_resilience_environment(monkeypatch)

    provider = get_chat_provider("openai")

    assert isinstance(provider, ResilientChatProvider)
    assert isinstance(provider.primary, OpenAIProvider)


def test_provider_factory_normalizes_name(monkeypatch):
    clear_resilience_environment(monkeypatch)

    provider = get_chat_provider("  MOCK  ")

    assert isinstance(provider.primary, MockProvider)


def test_provider_factory_rejects_unknown_provider(monkeypatch):
    clear_resilience_environment(monkeypatch)

    with pytest.raises(
        UnsupportedProviderError,
        match="Unsupported chat provider",
    ):
        get_chat_provider("unknown-provider")


def test_provider_factory_builds_explicit_fallback(monkeypatch):
    clear_resilience_environment(monkeypatch)
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("PROVIDER_FALLBACK_PROVIDER", "mock")
    monkeypatch.setenv(
        "PROVIDER_FALLBACK_MODEL",
        "mock-fallback-model",
    )

    provider = get_chat_provider("ollama")

    assert isinstance(provider.primary, OllamaProvider)
    assert isinstance(provider.fallback, MockProvider)
    assert provider.fallback_model == "mock-fallback-model"


def test_provider_factory_avoids_self_fallback(monkeypatch):
    clear_resilience_environment(monkeypatch)
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("PROVIDER_FALLBACK_PROVIDER", "mock")

    provider = get_chat_provider("mock")

    assert provider.fallback is None


def test_provider_factory_requires_fallback_name(monkeypatch):
    clear_resilience_environment(monkeypatch)
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "true")

    with pytest.raises(
        ProviderConfigurationError,
        match="PROVIDER_FALLBACK_PROVIDER is required",
    ):
        get_chat_provider("ollama")


def test_provider_factory_rejects_invalid_fallback(monkeypatch):
    clear_resilience_environment(monkeypatch)
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "true")
    monkeypatch.setenv(
        "PROVIDER_FALLBACK_PROVIDER",
        "unknown",
    )

    with pytest.raises(
        ProviderConfigurationError,
        match="Invalid PROVIDER_FALLBACK_PROVIDER",
    ):
        get_chat_provider("ollama")


def test_provider_factory_rejects_invalid_retry_range(monkeypatch):
    clear_resilience_environment(monkeypatch)
    monkeypatch.setenv("PROVIDER_RETRY_BASE_DELAY_MS", "200")
    monkeypatch.setenv("PROVIDER_RETRY_MAX_DELAY_MS", "100")

    with pytest.raises(
        ProviderConfigurationError,
        match="Invalid provider retry configuration",
    ):
        get_chat_provider("mock")
