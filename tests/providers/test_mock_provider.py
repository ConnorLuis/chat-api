import asyncio

from src.app.llm.providers import (
    MockProvider,
    ProviderChatRequest,
    ProviderMessage,
)


def build_request(
    *,
    model: str | None = None,
) -> ProviderChatRequest:
    return ProviderChatRequest(
        messages=(
            ProviderMessage(
                role="system",
                content="system instruction",
            ),
            ProviderMessage(
                role="user",
                content="hello",
            ),
        ),
        model=model,
        temperature=0.0,
        top_p=1.0,
        max_tokens=32,
    )


def test_mock_provider_chat_returns_unified_response():
    provider = MockProvider()
    response = provider.chat(build_request())

    assert response.content == "[mock] you said: hello"
    assert response.provider == "mock"
    assert response.model == "unknown"
    assert response.finish_reason == "stop"


def test_mock_provider_supports_model_override():
    provider = MockProvider()
    response = provider.chat(
        build_request(model="mock-test-model")
    )

    assert response.model == "mock-test-model"


def test_mock_provider_stream_returns_unified_chunks():
    provider = MockProvider()

    async def collect():
        return [
            chunk
            async for chunk in provider.stream(build_request())
        ]

    chunks = asyncio.run(collect())
    content = "".join(chunk.delta for chunk in chunks)

    assert content == (
        "[mock-stream] [mock] you said: hello"
    )
    assert all(chunk.provider == "mock" for chunk in chunks)
    assert all(chunk.model == "unknown" for chunk in chunks)
