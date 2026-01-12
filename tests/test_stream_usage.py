from fastapi.testclient import TestClient
from src.app.main import app

# 把 FastAPI 应用实例 app 传入 TestClient，创建一个模拟的 HTTP 客户端 client；
client = TestClient(app)

"""FastAPI 应用的 /chat/stream 流式接口（Mock 引擎正常场景）进行的 SSE 核心事件完整性测试
    验证：
        Mock 引擎生成的流式响应中，包含 meta（元信息）、token（增量内容）、usage（资源统计）、done（结束标识）四类核心 SSE 事件；
        确保流式响应的基础事件集完整，覆盖 “元信息 - 增量内容 - 资源统计 - 结束” 的全流程，前端能获取到所有关键事件。
"""
def test_stream_sse_contains_usage_and_done():
    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 16,
    }
    with client.stream("POST", "/chat/stream", json=payload) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")

        buf = "" # 初始化缓冲区
        for chunk in r.iter_text():# 逐段读取流式响应的文本内容（SSE 格式的字符串）
            buf += chunk
            if "event: done" in buf:
                break

        # 验证 SSE 事件的完整性
        assert "event: meta" in buf
        assert "event: token" in buf
        assert "event: usage" in buf
        assert "event: done" in buf