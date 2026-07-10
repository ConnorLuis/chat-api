from src.app.llm.providers import (
    OllamaProvider,
    ProviderChatRequest,
    ProviderMessage,
)


def test_ollama_provider_builds_generate_payload():
    provider = OllamaProvider(
        base_url="http://ollama.test",
        model="default-model",
        timeout_s=1,
    )

    request = ProviderChatRequest(
        messages=(
            ProviderMessage(
                role="system",
                content="be concise",
            ),
            ProviderMessage(
                role="user",
                content="hello",
            ),
        ),
        model="request-model",
        temperature=0.2,
        top_p=0.8,
        max_tokens=64,
    )

    payload = provider._build_payload(
        request,
        stream=False,
    )

    assert payload["model"] == "request-model"
    assert payload["stream"] is False
    assert payload["prompt"] == (
        "system: be concise\nuser: hello"
    )
    assert payload["options"] == {
        "temperature": 0.2,
        "top_p": 0.8,
        "num_predict": 64,
    }


def test_ollama_provider_uses_default_model():
    provider = OllamaProvider(
        base_url="http://ollama.test",
        model="default-model",
        timeout_s=1,
    )

    request = ProviderChatRequest(
        messages=(),
    )

    assert provider.resolve_model(request.model) == "default-model"
