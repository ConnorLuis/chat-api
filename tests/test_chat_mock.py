from fastapi.testclient import TestClient
from src.app.main import app

client = TestClient(app)

def test_chat_mock_ok():
    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 16
    }
    r = client.post("/chat", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "trace_id" in data
    assert "answer" in data
    assert "hi" in data["answer"]