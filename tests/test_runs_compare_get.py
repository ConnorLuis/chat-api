from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app.core.settings import settings
from src.app.main import app

client = TestClient(app)

"""
    测试/runs/compare/{compare_group_id}，验证是否：
        status 200
        compare_group_id 匹配
        records 长度 == 2（A/B）
        records[0].variant == "A"
        records[1].variant == "B"
        summary 不为空，并且包含：
        latency_ms_a/b/diff
        output_chars_a/b/diff
        bad_lines == 0
        
        **破坏性实验（测试版）**你可以这样做（不手改真实文件）：
            在临时 RUN_LOG_PATH 里手写一条坏 JSON 行（比如 {bad json)
            再调 compare get
            断言 bad_lines > 0 且接口仍能返回 200（鲁棒性）
"""

# 核心Fixture：创建临时日志目录，满足要求：设置临时 RUN_LOG_PATH
@pytest.fixture()
def run_log_path(tmp_path: Path, monkeypatch) -> Path:
    # 临时替换日志文件路径，测试结束自动销毁，不污染真实数据
    p = tmp_path / "prompt_runs.jsonl"
    monkeypatch.setenv("RUN_LOG_PATH", str(p))
    return p

def test_runs_compare_get_ok(run_log_path: Path):

    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "解释介绍RAG"}],
        "max_tokens": 128,
        "temperature": 0.7,
        "top_p": 0.9,
        "prompt_a": {"prompt_id": "chat", "prompt_version": "v1"},
        "prompt_b": {"prompt_id": "qa_strict", "prompt_version": "v1"}
    }

    prompt_compare_resp = client.post("/prompt/compare", json=payload)
    assert prompt_compare_resp.status_code == 200
    compare_group_id = prompt_compare_resp.json()["compare_group_id"]

    r = client.get(f"/runs/compare/{compare_group_id}")
    assert r.status_code == 200
    data = r.json()

    assert compare_group_id == data["compare_group_id"]
    assert data["bad_lines"] == 0
    assert len(data["records"]) == 2
    assert data["records"][0]["variant"] == "A"
    assert data["records"][1]["variant"] == "B"

    summary = data["summary"]
    assert summary is not None
    assert "latency_ms_a" in summary
    assert "latency_ms_b" in summary
    assert "diff_latency_ms" in summary
    assert "output_chars_a" in summary
    assert "output_chars_b" in summary
    assert "output_chars_diff" in summary

# 破坏性实验（测试版）
def test_runs_compare_bad_lines(run_log_path: Path):
    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "解释介绍RAG"}],
        "max_tokens": 128,
        "temperature": 0.7,
        "top_p": 0.9,
        "prompt_a": {"prompt_id": "chat", "prompt_version": "v1"},
        "prompt_b": {"prompt_id": "qa_strict", "prompt_version": "v1"}
    }
    compare_resp = client.post("/prompt/compare", json=payload)
    assert compare_resp.status_code == 200
    compare_group_id = compare_resp.json()["compare_group_id"]

    with run_log_path.open("a", encoding="utf-8") as f:
        f.write("{bad json line, no closing} \n")  # 无效JSON，会被统计为bad_lines

    r = client.get(f"/runs/compare/{compare_group_id}")
    assert r.status_code == 200  # 接口仍正常返回
    assert r.json()["bad_lines"] > 0  # 错误行计数>0