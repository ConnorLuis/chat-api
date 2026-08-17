from __future__ import annotations

from collections.abc import AsyncIterator

from src.app.api.openai_compat import (
    routes_chat_completions as routes_module,
)
from src.app.llm.providers import (
    ProviderChatChunk,
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderUsage,
)


class FakeProvider:
    name = "fake"

    def __init__(
        self,
        *,
        response_model: str = "fake-model",
        usage: ProviderUsage | None = None,
    ) -> None:
        self.response_model = response_model
        self.usage = usage
        self.requests: list[ProviderChatRequest] = []

    def resolve_model(
        self,
        requested_model: str | None = None,
    ) -> str:
        return requested_model or self.response_model

    def chat(
        self,
        request: ProviderChatRequest,
    ) -> ProviderChatResponse:
        self.requests.append(request)

        return ProviderChatResponse(
            content="fake provider answer",
            provider=self.name,
            model=self.response_model,
            usage=self.usage,
            finish_reason="length",
        )

    async def stream(
        self,
        request: ProviderChatRequest,
    ) -> AsyncIterator[ProviderChatChunk]:
        if False:
            yield ProviderChatChunk(
                delta="",
                provider=self.name,
                model=self.response_model,
            )


def test_non_stream_mock_returns_openai_shape(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "OPENAI_COMPAT_DEFAULT_PROVIDER",
        "mock",
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "mock-compatible-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"].startswith("chatcmpl-")
    assert data["object"] == "chat.completion"
    assert isinstance(data["created"], int)
    assert data["model"] == "mock-compatible-model"

    assert data["choices"] == [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "[mock] you said: hello",
            },
            "finish_reason": "stop",
            "logprobs": None,
        }
    ]

    # MockProvider 没有真实 token usage，不伪造零值。
    assert "usage" not in data

    execution = data["gateway"][
        "provider_execution"
    ]
    assert execution["primary_provider"] == "mock"
    assert execution["final_provider"] == "mock"
    assert execution["total_attempts"] == 1
    assert execution["retries"] == 0
    assert execution["fallback_used"] is False


def test_provider_override_and_usage_mapping(
    client,
    monkeypatch,
):
    fake_provider = FakeProvider(
        response_model="actual-provider-model",
        usage=ProviderUsage(
            prompt_tokens=12,
            completion_tokens=5,
            total_tokens=17,
        ),
    )

    captured_provider_names: list[str] = []

    def fake_factory(provider_name: str):
        captured_provider_names.append(provider_name)
        return fake_provider

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        fake_factory,
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "provider": "ollama",
            "model": "request-model",
            "messages": [
                {
                    "role": "system",
                    "content": "be concise",
                },
                {
                    "role": "user",
                    "content": "hello",
                },
            ],
            "temperature": 0.2,
            "top_p": 0.8,
            "max_completion_tokens": 64,
        },
    )

    assert response.status_code == 200
    assert captured_provider_names == ["ollama"]

    provider_request = fake_provider.requests[0]

    assert provider_request.model == "request-model"
    assert provider_request.temperature == 0.2
    assert provider_request.top_p == 0.8
    assert provider_request.max_tokens == 64

    data = response.json()

    assert data["model"] == "actual-provider-model"
    assert data["choices"][0]["finish_reason"] == "length"
    assert data["usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 5,
        "total_tokens": 17,
    }


def test_default_provider_comes_from_settings(
    client,
    monkeypatch,
):
    fake_provider = FakeProvider()
    captured_provider_names: list[str] = []

    monkeypatch.setenv(
        "OPENAI_COMPAT_DEFAULT_PROVIDER",
        "ollama",
    )

    def fake_factory(provider_name: str):
        captured_provider_names.append(provider_name)
        return fake_provider

    monkeypatch.setattr(
        routes_module,
        "get_chat_provider",
        fake_factory,
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "request-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert captured_provider_names == ["ollama"]



def test_n_greater_than_one_is_rejected(
    client,
):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "mock-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
            "n": 2,
        },
    )

    assert response.status_code == 400

    error = response.json()["error"]

    assert error["param"] == "n"
    assert error["code"] == "unsupported_value"


def test_request_validation_uses_openai_error_shape(
    client,
):
    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [],
            "unsupported_field": True,
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert set(data) == {"error"}
    assert data["error"]["type"] == (
        "invalid_request_error"
    )
    assert data["error"]["code"] == "invalid_request"


def test_openai_provider_missing_key_returns_502(
    client,
    monkeypatch,
):
    monkeypatch.delenv(
        "OPENAI_API_KEY",
        raising=False,
    )
    monkeypatch.delenv(
        "OPENAI_MODEL",
        raising=False,
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "provider": "openai",
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
        },
    )

    assert response.status_code == 502

    error = response.json()["error"]

    assert error["type"] == "api_error"
    assert error["code"] == "provider_error"
    assert "OPENAI_API_KEY" in error["message"]

    execution = response.json()["gateway"][
        "provider_execution"
    ]
    assert execution["primary_provider"] == "openai"
    assert execution["final_provider"] == "openai"
    assert execution["total_attempts"] == 1
    assert execution["attempts"][0][
        "error_code"
    ] == "provider_configuration_error"
