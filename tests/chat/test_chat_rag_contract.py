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

def test_chat_rag_contract(client, isolated_kb_env, monkeypatch):

    isolated_kb_env(collection_name="test_chat_rag")

    monkeypatch.setenv("KB_CHUNK_SIZE", "10000")
    monkeypatch.setenv("KB_CHUNK_OVERLAP", "0")

    kb_response = client.post(
        "/kb/documents",
        json={
            "text": "这是RAG测试文本，用于契约测试",
            "source": "test"
        }
    )
    assert kb_response.status_code == 200

    response = client.post(
        "/chat",
        json = {
            "provider": "mock",
            "messages": [{"role": "user", "content": "这是RAG测试文本，用于契约测试"}],
            "use_kb": True,
            "kb_top_k": 3
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    rag = data["metadata"].get("rag")
    assert_rag_observability(rag, backend="native")
    assert rag is not None
    assert rag["top_k"] == 3
    assert rag["enabled"] is True
    assert rag["hits"] >= 1
    citations = rag["citations"]
    assert isinstance(citations, list) and len(citations) >= 1
    c0 = citations[0]
    for k in ("doc_id", "chunk_id", "source"):
        assert k in c0 and str(c0[k]).strip() != ""

def test_chat_rag_contract_without_kb_data(client, isolated_kb_env):
    isolated_kb_env(collection_name="test_chat_rag_empty")
    response = client.post(
        "/chat",
        json={
            "provider": "mock",
            "messages": [{"role": "user", "content": "什么是RAG?"}],
            "use_kb": True,
            "kb_top_k": 3
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    rag = data["metadata"].get("rag")
    assert rag is not None
    assert rag["enabled"] is True
    assert rag["top_k"] == 3

    assert rag["citations"] == []
    assert rag["hits"] == 0