from fastapi.testclient import TestClient
from src.app.main import app

client = TestClient(app)

def test_stream_sse_mock_contains_done():
    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 16,
    }
    with client.stream("POST", "/chat/stream", json=payload) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        text = ""
        for chunk in r.iter_text():
            text += chunk
            if "event: done" in text:
                break
        assert "event: token" in text
        assert "event: done" in text