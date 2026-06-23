import pytest


pytest.importorskip("langchain_chroma")
pytest.importorskip("langchain_core")


def test_langchain_backend_chat_rag_contract(client, isolated_kb_env, monkeypatch):
    isolated_kb_env(collection_name="test_langchain_backend_rag")

    monkeypatch.setenv("RAG_BACKEND", "langchain")
    monkeypatch.setenv("KB_CHUNK_SIZE", "10000")
    monkeypatch.setenv("KB_CHUNK_OVERLAP", "0")

    kb_response = client.post(
        "/kb/documents",
        json={
            "text": "这是LangChain RAG后端测试文本，用于验证backend真正检索。",
            "source": "test-langchain",
            "title": "LangChain Backend Test",
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
                    "content": "这是LangChain RAG后端测试文本，用于验证backend真正检索。",
                }
            ],
            "use_kb": True,
            "kb_top_k": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    rag = data["metadata"]["rag"]

    assert rag["enabled"] is True
    assert rag["top_k"] == 3
    assert rag["hits"] >= 1
    assert rag["candidate_k"] >= 3
    assert rag["citations"]
    assert rag["error"] is None