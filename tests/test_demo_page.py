from fastapi.testclient import TestClient
from src.app.main import app

# 把 FastAPI 应用实例 app 传入 TestClient，创建一个模拟的 HTTP 客户端 client；
client = TestClient(app)

def test_demo_page_basic_contract():
    response = client.get("/demo")

    assert response.status_code == 200

    content_type = response.headers.get("content-type", "")
    assert "text/html" in content_type

    html_content = response.text.lower()

    assert "/chat/stream" in html_content
    assert "/prompt/compare" in html_content

    # 验证包含SSE事件相关关键字（确保SSE解析逻辑完整）
    assert "event:" in html_content
    assert "token" in html_content
    assert "meta" in html_content
    assert "usage" in html_content
    assert "done" in html_content