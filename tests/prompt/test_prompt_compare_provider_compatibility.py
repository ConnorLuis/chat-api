from fastapi.testclient import TestClient

from src.app.main import app


client = TestClient(app)


def test_prompt_compare_uses_provider_model_override():
    response = client.post(
        "/prompt/compare",
        json={
            "provider": "mock",
            "model": "mock-compare-model",
            "messages": [
                {
                    "role": "user",
                    "content": "compare this",
                }
            ],
            "prompt_a": {
                "prompt_id": "chat",
                "prompt_version": "v1",
                "prompt_vars": {},
            },
            "prompt_b": {
                "prompt_id": "qa_strict",
                "prompt_version": "v1",
                "prompt_vars": {},
            },
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 32,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["a"]["metadata"]["provider"] == "mock"
    assert data["b"]["metadata"]["provider"] == "mock"

    assert (
        data["a"]["metadata"]["model"]
        == "mock-compare-model"
    )
    assert (
        data["b"]["metadata"]["model"]
        == "mock-compare-model"
    )
