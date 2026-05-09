import pytest
from fastapi.testclient import TestClient

from src.app.core.settings import settings
from src.app.main import app

client = TestClient(app)

"""
    测试/runs/trace/{trace_id}，验证是否：
        status 200
        body.trace_id == trace_id
        body.records 长度 >= 1
        records[0] 至少包含：
        trace_id/provider/mode/latency_ms/prompt_id/prompt_version
        body.bad_lines == 0
        
        再补一个负例：
        
        查一个随机 trace_id → 404
"""

# 核心Fixture：创建临时日志目录，满足要求：设置临时 RUN_LOG_PATH
@pytest.fixture(autouse=True)
def tmp_run_log_path(tmp_path, monkeypatch):
    # 临时替换日志文件路径，测试结束自动销毁，不污染真实数据
    monkeypatch.setenv("RUN_LOG_PATH", str(tmp_path/"prompt_runs.jsonl"))
    yield

def test_runs_trace_get_ok():

    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hi. Who are you?"}],
        "max_tokens": 16,
        "prompt_id": "chat",
        "prompt_version": "v1"
    }
    chat_response = client.post("/chat", json=payload)
    assert chat_response.status_code == 200
    chat_data = chat_response.json()
    trace_id = chat_data["trace_id"]
    r = client.get(f"/runs/trace/{trace_id}")
    assert r.status_code == 200
    trace_data = r.json()
    assert trace_id == trace_data["trace_id"]
    assert len(trace_data["records"]) >= 1
    assert trace_data["bad_lines"] == 0

    record = trace_data["records"][0]
    assert record["trace_id"] == trace_id
    assert "provider" in record
    assert "mode" in record
    assert "latency_ms" in record
    assert "prompt_id" in record
    assert "prompt_version" in record

# 查一个随机 trace_id → 404
def test_runs_trace_not_found():
    # 补充负例
    wrong_trace_id = "00000000-d382-4f88-af42-334b57afbb00"
    r = client.get(f"/runs/trace/{wrong_trace_id}")
    assert r.status_code == 404
