# tests/test_stream_success_contract.py
import json
from fastapi.testclient import TestClient
from src.app.main import app

client = TestClient(app)

"""对 FastAPI 应用 /chat/stream 流式接口（Mock 引擎正常场景）进行的 全链路 SSE 事件契约测试
    验证：
        正常流式响应的事件序列严格遵循预设的 “契约流程”（meta 首事件 → token 增量事件 → usage 统计事件 → done 结束事件）；
        关键事件（meta/done）的 data 字段符合严格的数据规范，确保前端能按约定解析和使用所有事件数据。
"""

# 辅助函数（SSE 事件解析）
def _collect_sse_events(resp, max_events: int = 200) -> list[tuple[str, str]]:
    buf = ""
    events: list[tuple[str, str]] = []

    for chunk in resp.iter_text():
        buf += chunk

        while "\n\n" in buf:
            block, buf = buf.split("\n\n", 1)
            block = block.strip("\n")
            if not block.strip():
                continue

            event_type = None
            data_lines: list[str] = []

            for line in block.split("\n"):
                line = line.rstrip("\n")
                if line.startswith("event: "):
                    event_type = line.replace("event: ", "", 1).strip()
                elif line.startswith("data: "):
                    data_lines.append(line.replace("data: ", "", 1))

            # 最小健壮性：必须有 event 和 data
            assert event_type is not None, f"invalid SSE block (missing event): {block}"
            assert len(data_lines) >= 1, f"invalid SSE block (missing data): {block}"

            data_str = "\n".join(data_lines)  # data 可以多行
            events.append((event_type, data_str))

            if len(events) >= max_events:
                return events

            # 如果已经 done，直接结束收集
            if event_type == "done":
                return events

    return events

# 测试函数（核心契约验证）
def test_stream_success_contract_mock():
    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 32,
    }

    with client.stream("POST", "/chat/stream", json=payload) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")

        events = _collect_sse_events(r)

    # 事件类型列表
    event_types = [t for (t, _) in events]

    # meta 必须是第一个事件
    assert event_types[0] == "meta", f"first event must be meta, got: {event_types[0]}"

    # 至少有一个 token
    assert "token" in event_types, f"missing token events: {event_types}"

    # 必须包含 usage（成功流结束时统计）
    assert "usage" in event_types, f"missing usage event: {event_types}"

    # 最后必须 done
    assert event_types[-1] == "done", f"last event must be done, got: {event_types[-1]}"

    # done 的 data 应是 [DONE]
    done_data = events[-1][1].strip()
    assert done_data == "[DONE]"

    # meta data 至少包含 trace_id/provider/model
    meta_data = json.loads(events[0][1])
    assert "trace_id" in meta_data and meta_data["trace_id"]
    assert meta_data.get("provider") == "mock"
    assert "model" in meta_data and meta_data["model"]
