def test_kb_search_rejects_embedding_contract_drift(
    client,
    isolated_kb_env,
    monkeypatch,
):
    isolated_kb_env(collection_name="test_kb_index_contract_http")

    ingest = client.post(
        "/kb/documents",
        json={
            "title": "contract",
            "text": "persistent index contract test text",
            "source": "test",
        },
    )
    assert ingest.status_code == 200

    monkeypatch.setenv("EMBEDDING_DIM", "32")

    response = client.get(
        "/kb/search",
        params={"q": "contract", "top_k": 1},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "kb_index_contract_mismatch"
    assert "embedding_dim" in detail["message"]


def test_chat_rag_degrades_without_querying_mismatched_index(
    client,
    isolated_kb_env,
    monkeypatch,
):
    isolated_kb_env(collection_name="test_chat_index_contract_degrade")

    ingest = client.post(
        "/kb/documents",
        json={
            "title": "contract",
            "text": "persistent index contract test text",
            "source": "test",
        },
    )
    assert ingest.status_code == 200

    monkeypatch.setenv("EMBEDDING_DIM", "32")
    monkeypatch.setenv("RAG_BACKEND", "native")

    response = client.post(
        "/chat",
        json={
            "provider": "mock",
            "messages": [{"role": "user", "content": "contract"}],
            "use_kb": True,
            "kb_top_k": 1,
        },
    )

    assert response.status_code == 200
    rag = response.json()["metadata"]["rag"]
    assert rag["hits"] == 0
    assert "index contract mismatch" in rag["error"]
