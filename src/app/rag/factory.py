from src.app.core.settings import settings
from src.app.rag.base import RAGBackend
from src.app.rag.native_backend import NativeRAGBackend

def get_rag_backend() -> RAGBackend:
    backend = settings.RAG_BACKEND

    if backend == "native":
        return NativeRAGBackend()

    if backend == "langchain":
        from src.app.rag.langchain_backend import LangChainRAGBackend

        return LangChainRAGBackend()

    raise ValueError(
        f"Unsupported RAG_BACKEND={backend}. Choose from: native, langchain."
    )