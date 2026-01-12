from fastapi.testclient import TestClient
from src.app.main import app

client = TestClient(app)

"""对 FastAPI 应用的 /chat/stream 流式接口（Mock 引擎正常场景）进行的 SSE 事件完整性测试
    验证：
        Mock 引擎生成的流式响应中，不仅能返回 token 类型的增量内容事件，还会返回 done 类型的结束事件；
        确保流式响应遵循 “增量返回内容 → 发送结束标识” 的完整流程，前端能据此判断流式传输是否完成，避免无限等待。
"""
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