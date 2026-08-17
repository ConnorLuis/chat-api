import json

from fastapi.testclient import TestClient
from src.app.main import app

# 把 FastAPI 应用实例 app 传入 TestClient，创建一个模拟的 HTTP 客户端 client；
client = TestClient(app)

"""对 FastAPI 应用的 /chat/stream 流式接口进行的 Ollama 服务不可达场景下的 SSE 错误事件契约测试
    验证：
        异常场景下 /chat/stream 接口返回的 error 类型 SSE 事件中，data 字段的 JSON 数据严格符合预设契约 —— 包含所有必填溯源字段（trace_id/provider/model/latency_ms/error）；
        所有必填字段非空且有效，确保前端 / 运维能通过错误数据完整溯源问题，而非仅验证 “有 error 事件”。
"""
def test_stream_error_contract(monkeypatch):
    # 临时覆盖环境变量 OLLAMA_BASE_URL，指向本地 1 号端口（该端口几乎不会有服务监听）；
    # OllamaProvider 初始化时会读取这个错误的地址，调用 /api/generate 时会触发连接拒绝 / 超时错误；
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("PROVIDER_RETRY_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "false")

    payload = {
        "provider": "ollama",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 8,
    }

    with client.stream("POST", "/chat/stream", json=payload) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")

        buf = ""
        error_data_str = None
        # 读取一些chunk，然后停止
        for chunk in r.iter_text():
            buf += chunk
            if "event: error" in buf:
                lines = buf.split("\n")
                in_error_event = False
                for line in lines:
                    stripped_line = line.strip()
                    if stripped_line == "event: error":
                        in_error_event = True
                    elif in_error_event and stripped_line.startswith("data: "):
                        error_data_str = stripped_line.replace("data: ", "")
                        break
                break

        assert "event: error" in buf
        assert error_data_str is not None

        try:
            error_data = json.loads(error_data_str)
        except json.JSONDecodeError as e:
            assert False

        required_fields = ["trace_id", "provider", "model", "latency_ms", "error"]
        for field in required_fields:
            assert field in error_data
            # 额外断言字段非空（增强契约校验）
            assert error_data[field] is not None and str(error_data[field]).strip() != ""

        execution = error_data[
            "provider_execution"
        ]
        assert execution["primary_provider"] == "ollama"
        assert execution["final_provider"] == "ollama"
        assert execution["total_attempts"] == 1
        assert execution["fallback_used"] is False
        assert execution["attempts"][0][
            "error_code"
        ] == "provider_connection_error"
