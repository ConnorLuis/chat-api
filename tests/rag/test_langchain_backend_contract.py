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

def test_langchain_backend_build_context_exposes_backend_marker(client, isolated_kb_env, monkeypatch):
    isolated_kb_env(collection_name="test_langchain_backend_marker")

    monkeypatch.setenv("RAG_BACKEND", "langchain")
    monkeypatch.setenv("KB_CHUNK_SIZE", "10000")
    monkeypatch.setenv("KB_CHUNK_OVERLAP", "0")

    kb_response = client.post(
        "/kb/documents",
        json={
            "text": "这是LangChain backend marker测试文本，用于确认真正走langchain后端。",
            "source": "test-langchain-marker",
            "title": "LangChain Backend Marker Test",
        },
    )
    assert kb_response.status_code == 200

    from src.app.rag.factory import get_rag_backend

    backend = get_rag_backend()
    result = backend.build_context(
        query="这是LangChain backend marker测试文本，用于确认真正走langchain后端。",
        top_k=3,
    )

    assert result.enabled is True
    assert result.top_k == 3
    assert result.hits >= 1
    assert result.citations
    assert result.error is None
    assert result.extra["backend"] == "langchain"
    assert result.extra.get("vectorstore") == "langchain_chroma"