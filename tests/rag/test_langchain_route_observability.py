import json

import pytest


pytest.importorskip(
    "langchain_chroma",
    reason=(
        "optional LangChain RAG observability contract; install "
        "requirements-langchain.txt to run it"
    ),
)
pytest.importorskip(
    "langchain_core",
    reason=(
        "optional LangChain RAG observability contract; install "
        "requirements-langchain.txt to run it"
    ),
)


RAG_TIMING_KEYS = [
    "embedding_ms",
    "retrieval_ms",
    "rerank_ms",
    "context_build_ms",
    "total_ms",
]


def assert_langchain_rag_observability(rag: dict):
    assert rag["enabled"] is True
    assert rag["backend"] == "langchain"
    assert rag["vectorstore"] == "langchain_chroma"

    for key in RAG_TIMING_KEYS:
        assert key in rag
        assert isinstance(rag[key], int)
        assert rag[key] >= 0

    assert rag["retrieval_mode"] == "hybrid"
    assert rag["fusion"] == "vector_lexical"
    assert rag["vector_weight"] == 0.7
    assert rag["lexical_weight"] == 0.3


def parse_sse_events(text: str) -> list[tuple[str, str]]:
    events = []

    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue

        event_name = None
        data_lines = []

        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").lstrip())

        events.append((event_name, "\n".join(data_lines)))

    return events


def get_json_event(events: list[tuple[str, str]], event_name: str) -> dict:
    for name, data in events:
        if name == event_name:
            return json.loads(data)

    raise AssertionError(f"missing SSE event: {event_name}")


def test_chat_response_exposes_langchain_rag_observability(client, isolated_kb_env, monkeypatch):
    isolated_kb_env(collection_name="test_langchain_route_observability_chat")

    monkeypatch.setenv("RAG_BACKEND", "langchain")
    monkeypatch.setenv("KB_CHUNK_SIZE", "10000")
    monkeypatch.setenv("KB_CHUNK_OVERLAP", "0")

    kb_response = client.post(
        "/kb/documents",
        json={
            "text": "这是LangChain route observability测试文本，用于验证接口层返回backend和timing字段。",
            "source": "test-langchain-route-observability",
            "title": "LangChain Route Observability Test",
        },
    )
    assert kb_response.status_code == 200

    response = client.post(
        "/chat",
        json={
            "provider": "mock",
            "messages": [
                {
                    "role": "user",
                    "content": "这是LangChain route observability测试文本，用于验证接口层返回backend和timing字段。",
                }
            ],
            "use_kb": True,
            "kb_top_k": 3,
        },
    )

    assert response.status_code == 200

    data = response.json()
    rag = data["metadata"]["rag"]

    assert rag["hits"] >= 1
    assert rag["citations"]
    assert rag["error"] is None
    assert_langchain_rag_observability(rag)


def test_stream_response_exposes_langchain_rag_observability(client, isolated_kb_env, monkeypatch):
    isolated_kb_env(collection_name="test_langchain_route_observability_stream")

    monkeypatch.setenv("RAG_BACKEND", "langchain")
    monkeypatch.setenv("KB_CHUNK_SIZE", "10000")
    monkeypatch.setenv("KB_CHUNK_OVERLAP", "0")

    kb_response = client.post(
        "/kb/documents",
        json={
            "text": "这是LangChain stream route observability测试文本，用于验证SSE返回backend和timing字段。",
            "source": "test-langchain-stream-route-observability",
            "title": "LangChain Stream Route Observability Test",
        },
    )
    assert kb_response.status_code == 200

    response = client.post(
        "/chat/stream",
        json={
            "provider": "mock",
            "messages": [
                {
                    "role": "user",
                    "content": "这是LangChain stream route observability测试文本，用于验证SSE返回backend和timing字段。",
                }
            ],
            "use_kb": True,
            "kb_top_k": 3,
        },
    )

    assert response.status_code == 200

    events = parse_sse_events(response.text)
    meta = get_json_event(events, "meta")
    usage = get_json_event(events, "usage")

    assert "rag" in meta
    assert "rag" in usage

    assert_langchain_rag_observability(meta["rag"])
    assert_langchain_rag_observability(usage["rag"])

    assert usage["rag"]["hits"] >= 1
    assert usage["rag"]["citations"]
    assert usage["rag"]["error"] is None