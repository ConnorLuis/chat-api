def test_kb_ingest_contract(client, isolated_kb_env):

    paths = isolated_kb_env(collection_name="test_kb_ingest")

    response = client.post(
        "/kb/documents",
        json={
            "title": "测试文档",
            "text": "这是RAG测试文本，用于契约测试",
            "source": "test"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "doc_id" in data
    assert "chunks" in data
    assert "metadata" in data
    assert data["metadata"]["trace_id"] is not None
    assert type(data["metadata"]["latency_ms"]) is int
    assert data["metadata"]["latency_ms"] >= 0


    assert isinstance(data.get("doc_id"), str) and data["doc_id"].strip()
    assert isinstance(data.get("chunks"), int) and data["chunks"] > 0
    assert isinstance(data["metadata"].get("trace_id"), str) and data["metadata"]["trace_id"].strip()
    assert isinstance(data["metadata"].get("latency_ms"), int) and data["metadata"]["latency_ms"] >= 0

    doc_id = data["doc_id"]
    doc_path = paths["kb_dir"] / "docs" / f"{doc_id}.md"
    assert doc_path.exists()

    index_path = paths["kb_dir"] / "docs.jsonl"
    assert index_path.exists()
    assert doc_id in index_path.read_text(encoding="utf-8")