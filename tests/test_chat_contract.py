from fastapi.testclient import TestClient
from src.app.main import app

# 把 FastAPI 应用实例 app 传入 TestClient，创建一个模拟的 HTTP 客户端 client；
client = TestClient(app)

"""对 FastAPI 聊天接口 /chat（同步非流式接口）进行的 “契约测试（Contract Test）
    验证：
        接口在正常场景下（使用 mock 引擎）能返回 200 成功响应；
        响应数据完全符合 ChatResponse 模型定义的 “数据契约”（字段完整性、关键字段值的正确性）；
        确保接口的输入输出格式稳定，不会因代码变更破坏前后端约定的字段结构。
"""
def test_chat_contract_ok():

    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "hi"}],
    }

    r = client.post("/chat", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["metadata"]["provider"] == "mock"
    assert "latency_ms" in data["metadata"]
    assert "trace_id" in data
    assert "answer" in data
    assert "model" in data["metadata"]