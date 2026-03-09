import pytest
import json
import os
from fastapi.testclient import TestClient
from src.app.main import app


client = TestClient(app)


@pytest.fixture
def temp_run_log(tmp_path, monkeypatch):
    """创建临时日志文件路径，注入环境变量"""
    log_path = tmp_path / "test_runs.jsonl"
    monkeypatch.setenv("RUN_LOG_PATH", str(log_path))
    # 确保初始状态文件不存在
    if os.path.exists(log_path):
        os.remove(log_path)
    return log_path


def test_run_log_writing_chat(temp_run_log):
    """测试同步Chat接口的运行日志写入"""
    # 调用同步Chat接口
    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "test run log sync"}],
        "max_tokens": 64,
        "prompt_id": "chat",
        "prompt_version": "v1"
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200

    # 验证日志文件存在且内容合法
    assert os.path.exists(temp_run_log), "日志文件未生成"
    with open(temp_run_log, "r", encoding="utf-8") as f:
        log_entries = [json.loads(line.strip()) for line in f if line.strip()]

    # 断言日志条目数量和核心字段
    assert len(log_entries) == 1, "同步接口应生成1条日志"
    entry = log_entries[0]
    _validate_log_entry(entry, mode="chat")


def test_run_log_writing_stream(temp_run_log):
    """测试流式Chat接口的运行日志写入"""
    # 调用流式Chat接口（需读取完流确保请求完成）
    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "test run log stream"}],
        "max_tokens": 64,
        "prompt_id": "qa_strict",
        "prompt_version": "v1"
    }
    with client.stream("POST", "/chat/stream", json=payload) as response:
        assert response.status_code == 200
        # 读取所有流式响应行（确保请求执行完成）
        for _ in response.iter_text():
            pass

    # 验证日志文件存在且内容合法
    assert os.path.exists(temp_run_log), "日志文件未生成"
    with open(temp_run_log, "r", encoding="utf-8") as f:
        log_entries = [json.loads(line.strip()) for line in f if line.strip()]

    # 断言日志条目数量和核心字段
    assert len(log_entries) == 1, "流式接口应生成1条日志"
    entry = log_entries[0]
    _validate_log_entry(entry, mode="stream")


def _validate_log_entry(entry, mode):
    """通用日志条目验证函数"""
    required_fields = ["trace_id", "provider", "latency_ms", "mode", "prompt_id", "prompt_version"]
    for field in required_fields:
        assert field in entry, f"日志缺少核心字段：{field}"

    # 字段值验证
    assert entry["provider"] == "mock", "provider字段值错误"
    assert entry["mode"] == mode, f"mode字段应为{mode}"
    assert isinstance(entry["latency_ms"], int) and entry["latency_ms"] >= 0, "latency_ms格式错误"