from fastapi.testclient import TestClient
from src.app.main import app

# 把 FastAPI 应用实例 app 传入 TestClient，创建一个模拟的 HTTP 客户端 client；
client = TestClient(app)

"""对 FastAPI 聊天接口 /chat（同步非流式接口）的 “异常场景契约测试”
    验证：
        当 Ollama 服务不可达时，/chat 接口能返回符合预期的 502 错误状态码；
        错误响应的结构完全符合 ErrorResponse 模型定义的 “数据契约”（字段完整性、层级正确性）；
        确保接口在异常场景下返回的错误信息包含排查问题所需的全部关键字段，不会遗漏核心溯源信息。
"""
def test_chat_error_contract_ok(monkeypatch):

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

    r = client.post("/chat", json=payload)
    assert r.status_code == 502
    data = r.json()["detail"]
    assert "trace_id" in data
    assert "provider" in data
    assert "model" in data
    assert "latency_ms" in data
    assert "error" in data
    execution = data["provider_execution"]
    assert execution["primary_provider"] == "ollama"
    assert execution["final_provider"] == "ollama"
    assert execution["total_attempts"] == 1
    assert execution["fallback_used"] is False
    assert execution["attempts"][0]["outcome"] == "failed"
    assert execution["attempts"][0]["error_code"] == (
        "provider_connection_error"
    )
