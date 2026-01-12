from fastapi.testclient import TestClient
from src.app.main import app

# 把 FastAPI 应用实例 app 传入 TestClient，创建一个模拟的 HTTP 客户端 client；
client = TestClient(app)

"""对 FastAPI 聊天接口 /chat（同步非流式接口）的 “Mock 引擎正常场景功能测试”
    验证:
        当使用 mock 引擎发起请求时，/chat 接口能返回 200 成功响应；
        响应包含核心业务字段（trace_id/answer），且 mock 引擎能正确生成包含用户输入内容的模拟回复，确保 Mock 引擎的核心功能符合预期。
"""
def test_chat_mock_ok():
    # 构建请求参数
    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 16
    }
    # 调用接口
    r = client.post("/chat", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "trace_id" in data
    assert "answer" in data
    assert "hi" in data["answer"]