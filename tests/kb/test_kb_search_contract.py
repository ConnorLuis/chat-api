def test_kb_search_contract(client, isolated_kb_env, monkeypatch):
    paths = isolated_kb_env(collection_name="test_kb_search")

    monkeypatch.setenv("KB_CHUNK_SIZE", "10000")
    monkeypatch.setenv("KB_CHUNK_OVERLAP", "0")

    text = "RAG是检索增强生成。这里是契约测试专用文本。"
    ingest_resp = client.post(
        "/kb/documents",
        json={
            "text": text,
            "source": "test"
        }
    )
    assert ingest_resp.status_code == 200
    doc_id = ingest_resp.json()["doc_id"]
    assert isinstance(doc_id, str) and doc_id.strip()

    search_resp = client.get("/kb/search", params={"q": text, "top_k": 3})
    assert search_resp.status_code == 200
    data = search_resp.json()

    assert data["query"] == text
    assert data["top_k"] == 3
    assert "metadata" in data
    assert isinstance(data["metadata"].get("trace_id"), str) and data["metadata"]["trace_id"].strip()
    assert isinstance(data["metadata"].get("latency_ms"), int) and data["metadata"]["latency_ms"] >= 0

    assert "hits" in data and isinstance(data["hits"], list)
    assert len(data["hits"]) >= 1

    hit0 = data["hits"][0]
    assert hit0["doc_id"] == doc_id
    assert isinstance(hit0["chunk_id"], str) and hit0["chunk_id"].strip()
    assert isinstance(hit0["text"], str) and hit0["text"].strip()
    assert isinstance(hit0["source"], str) and hit0["source"].strip()
    assert isinstance(hit0["score"], (int, float))

def test_kb_search_empty_query_returns_400(client, isolated_kb_env):
    isolated_kb_env(collection_name="test_kb_search_empty")

    r = client.get("/kb/search", params={"q": "     ", "top_k": 3})
    assert r.status_code == 400