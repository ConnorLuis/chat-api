import os
from fastapi.testclient import TestClient
from src.app.main import app

"""异常场景测试用例，
    核心目标是验证：当 Ollama 服务无法访问时，/chat/stream 接口仍能返回合规的 SSE 流式响应（200 状态码 + text/event-stream 格式），
    并在 SSE 事件中推送 meta（元信息）和 error（错误信息）事件，而非直接返回 5xx 错误，保证前端能优雅处理异常。
"""

# 把 FastAPI 应用实例 app 传入 TestClient，创建一个模拟的 HTTP 客户端 client；
client = TestClient(app)

def test_stream_sse_error_when_ollama_unreachable(monkeypatch):
    # 临时覆盖环境变量 OLLAMA_BASE_URL，指向本地 1 号端口（该端口几乎不会有服务监听）；
    # OllamaEngine 初始化时会读取这个错误的地址，调用 /api/generate 时会触发连接拒绝 / 超时错误；
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")

    payload = {
        "provider": "ollama",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 8,
    }

    with client.stream("POST", "/chat/stream", json=payload) as r:
        assert r.status_code == 200  # 返回status仍然是200, 错误在SSE
        assert r.headers["content-type"].startswith("text/event-stream")

        buf = ""
        # 读取一些chunk，然后停止
        for chunk in r.iter_text():
            buf += chunk
            if "event: error" in buf:
                break

        assert "event: meta" in buf
        assert "event: error" in buf