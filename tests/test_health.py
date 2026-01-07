from fastapi.testclient import TestClient
from src.app.main import app

# 把 FastAPI 应用实例 app 传入 TestClient，创建一个模拟的 HTTP 客户端 client；
client = TestClient(app)

# 定义测试用例函数
def test_health_ok():
    # 调用接口
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
