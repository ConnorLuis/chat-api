import json
import os.path

import pytest
from src.app.main import app

from fastapi.testclient import TestClient

client = TestClient(app)

@pytest.fixture
def mock_run_log_path(tmp_path, monkeypatch):
    """创建临时RUN_LOG_PATH并注入环境变量"""
    log_path = tmp_path / "runs.jsonl"
    monkeypatch.setenv("RUN_LOG_PATH", str(log_path))
    return log_path

def test_chat_prompt_registry_sync(mock_run_log_path):
    """测试同步Chat接口的Prompt ID/Version插入及日志写入"""
    # 构造测试请求体
    test_payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 128,
        "temperature": 0.7,
        "top_p": 0.9,
        "prompt_id": "chat",
        "prompt_version": "v1",
        "prompt_vars": {}
    }

    # 发送POST请求
    response =client.post("/chat", json=test_payload)

    # 断言HTTP状态码200
    assert response.status_code == 200, f"预期状态码200，实际{response.status_code}"

    # 断言响应metadata包含prompt_id/version
    response_data = response.json()
    metadata = response_data.get("metadata", {})
    assert metadata.get("prompt_id") == "chat", "metadata中的prompt_id不匹配"
    assert metadata.get("prompt_version") == "v1", "metadata中prompt_version不匹配"

    # 断言运行日志文件存在且内容合法
    assert os.path.exists(mock_run_log_path), "运行日志文件未生成"

    with open(mock_run_log_path, "r", encoding="utf-8") as f:
        log_lines = [line.strip() for line in f if line.strip()]
        assert len(log_lines) == 1, "日志文件应仅包含一行记录"

        # 解析日志条目并验证核心字段
        log_entry= json.loads(log_lines[0])
        assert "trace_id" in log_entry, "日志缺少trace_id字段"
        assert log_entry["provider"] == "mock", "日志provider字段错误"
        assert log_entry["prompt_id"] == "chat", "日志prompt_id字段错误"
        assert log_entry["prompt_version"] == "v1", "日志prompt_version字段错误"
        assert "latency_ms" in log_entry, "日志缺少latency_ms字段"
        assert log_entry["mode"] == "chat", "日志mode字段错误"