import pytest

from src.app.llm.providers import (
    OpenAIProvider,
    ProviderChatRequest,
    ProviderConfigurationError,
    ProviderMessage,
)


def build_request(
    *,
    model: str | None = "test-model",
) -> ProviderChatRequest:
    return ProviderChatRequest(
        messages=(
            ProviderMessage(
                role="user",
                content="hello",
            ),
        ),
        model=model,
        max_tokens=16,
    )


def test_openai_provider_can_be_imported_without_sdk_call():
    provider = OpenAIProvider(
        api_key="",
        model="test-model",
    )

    assert provider.name == "openai"
    assert provider.resolve_model(None) == "test-model"


def test_openai_provider_requires_api_key_before_call():
    provider = OpenAIProvider(
        api_key="",
        model="test-model",
    )

    with pytest.raises(
        ProviderConfigurationError,
        match="OPENAI_API_KEY",
    ):
        provider.chat(build_request())


def test_openai_provider_requires_model():
    provider = OpenAIProvider(
        api_key="test-key",
        model="",
    )

    with pytest.raises(
        ProviderConfigurationError,
        match="OpenAI model is required",
    ):
        provider.chat(build_request(model=None))
