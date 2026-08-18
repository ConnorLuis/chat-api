from fastapi.testclient import TestClient

from src.app.main import app


client = TestClient(app)


def test_chat_uses_provider_layer_and_model_override():
    response = client.post(
        "/chat",
        json={
            "provider": "mock",
            "model": "mock-request-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello provider",
                }
            ],
            "max_tokens": 32,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == (
        "[mock] you said: hello provider"
    )
    assert data["metadata"]["provider"] == "mock"
    assert data["metadata"]["model"] == "mock-request-model"


def test_chat_accepts_openai_provider_schema(
    monkeypatch,
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    response = client.post(
        "/chat",
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

    # OpenAI Provider 已进入主链路；当前未配置真实密钥时，
    # 应是下游 Provider 配置错误映射成 502，而不是 schema 422。
    assert response.status_code == 502

    detail = response.json()["detail"]

    assert detail["provider"] == "openai"
    assert detail["model"] == "test-model"
    assert "OPENAI_API_KEY" in detail["error"]
