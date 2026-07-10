import pytest

from src.app.llm.providers import (
    MockProvider,
    OllamaProvider,
    OpenAIProvider,
    UnsupportedProviderError,
    get_chat_provider,
)


def test_provider_factory_returns_mock_provider():
    provider = get_chat_provider("mock")
    assert isinstance(provider, MockProvider)


def test_provider_factory_returns_ollama_provider():
    provider = get_chat_provider("ollama")
    assert isinstance(provider, OllamaProvider)


def test_provider_factory_returns_openai_provider():
    provider = get_chat_provider("openai")
    assert isinstance(provider, OpenAIProvider)


def test_provider_factory_normalizes_name():
    provider = get_chat_provider("  MOCK  ")
    assert isinstance(provider, MockProvider)


def test_provider_factory_rejects_unknown_provider():
    with pytest.raises(
        UnsupportedProviderError,
        match="Unsupported chat provider",
    ):
        get_chat_provider("unknown-provider")
