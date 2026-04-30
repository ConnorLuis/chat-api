from starlette.testclient import TestClient

from src.app.main import app

client = TestClient(app)

def test_prompt_compare_contract():

    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "解释介绍RAG"}],
        "max_tokens": 128,
        "temperature": 0.7,
        "top_p": 0.9,
        "prompt_a": {"prompt_id": "chat", "prompt_version": "v1"},
        "prompt_b": {"prompt_id": "qa_strict", "prompt_version": "v1"}
    }
    r = client.post("/prompt/compare", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "compare_group_id" in data
    assert "a" in data
    assert "b" in data
    assert "metrics" in data
    assert "provider" in data["a"]["metadata"]
    assert "model" in data["a"]["metadata"]
    assert "latency_ms" in data["a"]["metadata"]
    assert "prompt_id" in data["a"]["metadata"]
    assert "prompt_version" in data["a"]["metadata"]

    assert "provider" in data["b"]["metadata"]
    assert "model" in data["b"]["metadata"]
    assert "latency_ms" in data["b"]["metadata"]
    assert "prompt_id" in data["b"]["metadata"]
    assert "prompt_version" in data["b"]["metadata"]

    assert "latency_ms_a" in data["metrics"]
    assert "latency_ms_b" in data["metrics"]
    assert "diff_latency_ms" in data["metrics"]
    assert "output_chars_a" in data["metrics"]
    assert "output_chars_b" in data["metrics"]
    assert "output_chars_diff" in data["metrics"]

