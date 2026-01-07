from fastapi.testclient import TestClient
from src.app.main import app

# 把 FastAPI 应用实例 app 传入 TestClient，创建一个模拟的 HTTP 客户端 client；
client = TestClient(app)

# 定义测试用例函数
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