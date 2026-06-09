import pytest

from src.app.rag.factory import get_rag_backend
from src.app.rag.native_backend import NativeRAGBackend

def test_default_rag_backend_is_native(monkeypatch):
    monkeypatch.delenv("RAG_BACKEND", raising=False)

    backend = get_rag_backend()

    assert isinstance(backend, NativeRAGBackend)

def test_invalid_rag_backend_raises(monkeypatch):
    monkeypatch.setenv("RAG_BACKEND", "invalid")

    with pytest.raises(ValueError) as e:
        get_rag_backend()

    assert "Unsupported RAG_BACKEND" in str(e.value)


def test_langchain_backend_missing_dependency_has_clear_error(monkeypatch):
    monkeypatch.setenv("RAG_BACKEND", "langchain")

    try:
        backend = get_rag_backend()
    except RuntimeError as e:
        assert "requirements-langchain.txt" in str(e)
    else:
        assert backend.__class__.__name__ == "LangChainRAGBackend"

