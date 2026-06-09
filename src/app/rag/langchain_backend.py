from src.app.rag.base import RAGBackend
from src.app.rag.schemas import RAGContextResult


class LangChainRAGBackend(RAGBackend):
    def __init__(self):
        try:
            import langchain  # noqa: F401
            from langchain_ollama import ChatOllama  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "RAG_BACKEND=langchain requires optional dependencies. "
                "Install with `pip install -r requirements-langchain.txt`."
            ) from e

    def build_context(self, query: str, top_k: int) -> RAGContextResult:
        return RAGContextResult(
            enabled=True,
            top_k=top_k,
            hits=0,
            candidate_k=0,
            context="",
            context_chars=0,
            citations=[],
            error="langchain backend skeleton is not implemented yet",
            extra={"backend": "langchain"},
        )