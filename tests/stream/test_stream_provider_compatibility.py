import json

from fastapi.testclient import TestClient

from src.app.main import app


client = TestClient(app)


def parse_sse_events(body: str) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []

    normalized = body.replace("\r\n", "\n")

    for block in normalized.split("\n\n"):
        # 不能使用 strip()，因为 payload 本身可能是空格。
        block = block.strip("\n")
        if not block.strip():
            continue

        event_name = None
        data_lines: list[str] = []

        for line in block.split("\n"):
            if line.startswith("event:"):
                value = line[len("event:"):]

                if value.startswith(" "):
                    value = value[1:]

                event_name = value

            elif line.startswith("data:"):
                value = line[len("data:"):]

                # 只删除 SSE 字段冒号后的一个可选分隔空格。
                # 不使用 lstrip()，避免删除真实空格 token。
                if value.startswith(" "):
                    value = value[1:]

                data_lines.append(value)

        if event_name is not None:
            events.append(
                (
                    event_name,
                    "\n".join(data_lines),
                )
            )

    return events


def test_stream_uses_provider_layer_and_model_override():
    response = client.post(
        "/chat/stream",
        json={
            "provider": "mock",
            "model": "mock-stream-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello stream",
                }
            ],
            "max_tokens": 32,
        },
    )

    assert response.status_code == 200

    events = parse_sse_events(response.text)
    event_names = [name for name, _ in events]

    assert event_names[0] == "meta"
    assert "token" in event_names
    assert "usage" in event_names
    assert event_names[-1] == "done"

    meta_payload = json.loads(events[0][1])

    assert meta_payload["provider"] == "mock"
    assert meta_payload["model"] == "mock-stream-model"

    token_payloads = [
        data
        for name, data in events
        if name == "token"
    ]

    assert "".join(token_payloads) == (
        "[mock-stream] [mock] you said: hello stream"
    )

    # Provider 的空 delta 分片不能被暴露为空 token 事件。
    assert all(token != "" for token in token_payloads)
