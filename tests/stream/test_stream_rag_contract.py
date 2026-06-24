import json

RAG_TIMING_KEYS = [
    "embedding_ms",
    "retrieval_ms",
    "rerank_ms",
    "context_build_ms",
    "total_ms",
]


def assert_rag_observability(rag: dict, backend: str = "native"):
    assert rag["backend"] == backend

    for key in RAG_TIMING_KEYS:
        assert key in rag
        assert isinstance(rag[key], int)
        assert rag[key] >= 0

def _parse_sse(text: str):
    events = []
    for block in text.split("\n\n"):
        block = block.strip("\n")
        if not block.strip():
            continue
        lines = block.splitlines()
        ev = None
        data_lines = []
        for ln in lines:
            if ln.startswith("event:"):
                ev = ln.split(":", 1)[1].strip()
            elif ln.startswith("data:"):
                data_lines.append(ln.split(":", 1)[1].lstrip())

        data = "\n".join(data_lines)
        events.append((ev, data))
    return events

def test_stream_rag_contract_ok(client, isolated_kb_env):
    isolated_kb_env(collection_name="test_stream_rag_ok")

    ingest = client.post("/kb/documents", json={
        "title": "kb demo",
        "text": "RAG 最小闭环：ingest->chunk->embedding->retrieve->inject->generate。",
        "source": "test",
    })

    assert ingest.status_code == 200

    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "什么是RAG最小闭环？"}],
        "use_kb": True,
        "kb_top_k": 3,
        "prompt_id": "chat",
        "prompt_version": "v1",
        "max_tokens": 64,
    }

    with client.stream("POST", "/chat/stream", json=payload) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        text = "".join(r.iter_text())

    events = _parse_sse(text)
    types = [t for (t, _) in events]

    assert types[0] == "meta"
    assert types[-1] == "done"
    assert "token" in types
    assert "usage" in types

    meta = json.loads(events[0][1])
    assert_rag_observability(meta["rag"], backend="native")
    assert meta["rag"]["enabled"] is True
    assert meta["rag"]["top_k"] == 3
    assert meta["rag"]["hits"] >= 1
    assert meta["rag"]["context_chars"] >= 0

    usage = None
    for t, d in events:
        if t == "usage":
            usage = json.loads(d)
            break

    assert usage is not None
    assert_rag_observability(usage["rag"], backend="native")
    assert usage["rag"]["enabled"] is True
    assert isinstance(usage["rag"]["citations"], list)
    assert len(usage["rag"]["citations"]) >= 1
    c0 = usage["rag"]["citations"][0]
    assert "doc_id" in c0 and c0["doc_id"]
    assert "chunk_id" in c0 and c0["chunk_id"]
    assert "source" in c0 and c0["source"]

    done_data = events[-1][1].strip()
    assert done_data == "[DONE]"

def test_stream_rag_degrade_ok_when_kb_empty(client, isolated_kb_env):
    isolated_kb_env(collection_name="test_stream_rag_empty")

    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "hi"}],
        "use_kb": True,
        "kb_top_k": 3,
        "max_tokens": 16,
    }

    with client.stream("POST", "/chat/stream", json=payload) as r:
        assert r.status_code == 200
        text = "".join(r.iter_text())

    events = _parse_sse(text)
    meta = json.loads(events[0][1])
    assert meta["rag"]["enabled"] is True
    assert meta["rag"]["hits"] == 0

    usage = None
    for t, d in events:
        if t == "usage":
            usage = json.loads(d)
            break

    assert usage is not None
    assert usage["rag"]["hits"] == 0
    assert usage["rag"]["citations"] == []