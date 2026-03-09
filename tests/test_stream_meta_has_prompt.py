import json

from src.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_stream_meta_has_prompt_id_version():
    """测试流式Chat接口的meta事件包含prompt_id/version"""
    # 构建测试请求体
    test_payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 128,
        "temperature": 0.7,
        "top_p": 0.9,
        "prompt_id": "qa_strict",
        "prompt_version": "v1",
        "prompt_vars": {}
    }

    # 发送流式POST请求（stream=True）
    with client.stream("POST", "/chat/stream", json=test_payload) as response:
        # 1. 断言HTTP状态码200
        assert response.status_code == 200, f"预期状态码200，实际{response.status_code}"

        # 2. 解析SSE响应，提取meta事件
        meta_data = None
        lines = response.iter_lines()
        for line in lines:
            if not line:
                continue
            # 解码字节流为字符串（兼容不同Python版本）
            line_str = line.decode("utf-8") if isinstance(line, bytes) else line

            # 找到meta事件行
            if line_str.startswith("event: meta"):
                # 读取下一行的data内容
                raw = next(lines)
                data_line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if data_line.startswith("data: "):
                    meta_json = data_line.replace("data: ", "")
                    meta_data = json.loads(meta_json)
                    break

    # 断言meta事件包含目标字段
    assert meta_data is not None, "未找到meta事件"
    assert meta_data["prompt_id"] == "qa_strict", "meta事件prompt_id不匹配"
    assert meta_data["prompt_version"] == "v1", "meta事件prompt_version不匹配"
    assert meta_data["provider"] == "mock", "meta事件provider字段错误"
    assert "trace_id" in meta_data, "meta事件缺少trace_id字段"