def test_native_backend_build_context_exposes_timing(client, isolated_kb_env, monkeypatch):
    isolated_kb_env(collection_name="test_native_backend_timing")

    monkeypatch.setenv("RAG_BACKEND", "native")
    monkeypatch.setenv("KB_CHUNK_SIZE", "10000")
    monkeypatch.setenv("KB_CHUNK_OVERLAP", "0")

    kb_response = client.post(
        "/kb/documents",
        json={
            "text": "这是Native RAG backend timing测试文本，用于验证可观测性字段。",
            "source": "test-native-timing",
            "title": "Native Backend Timing Test",
        },
    )
    assert kb_response.status_code == 200

    from src.app.rag.factory import get_rag_backend

    backend = get_rag_backend()
    result = backend.build_context(
        query="这是Native RAG backend timing测试文本，用于验证可观测性字段。",
        top_k=3,
    )

    assert result.enabled is True
    assert result.top_k == 3
    assert result.hits >= 1
    assert result.citations
    assert result.error is None
    assert result.extra["backend"] == "native"
    assert result.extra["retrieval_mode"] == "hybrid"
    assert result.extra["fusion"] == "vector_lexical"
    assert result.extra["vector_weight"] == 0.7
    assert result.extra["lexical_weight"] == 0.3

    for key in [
        "embedding_ms",
        "retrieval_ms",
        "rerank_ms",
        "context_build_ms",
        "total_ms",
    ]:
        assert key in result.extra
        assert isinstance(result.extra[key], int)
        assert result.extra[key] >= 0