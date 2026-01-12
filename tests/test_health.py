from fastapi.testclient import TestClient
from src.app.main import app

# 把 FastAPI 应用实例 app 传入 TestClient，创建一个模拟的 HTTP 客户端 client；
client = TestClient(app)

"""对 FastAPI 应用的 健康检查接口 /health 进行的基础功能测试
    验证：
        健康检查接口可正常访问，返回 200 成功状态码；
        接口返回的响应数据符合约定，核心字段 status 的值为 "ok"，确保应用服务处于正常运行状态。
"""
def test_health_ok():
    # 调用接口
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
