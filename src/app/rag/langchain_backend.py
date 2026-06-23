from src.app.core.settings import settings
from src.app.kb.embeddings import get_embedding_engine
from src.app.kb.rag_context import build_rag_context, rerank_hits
from src.app.kb.schemas import Hit
from src.app.rag.base import RAGBackend
from src.app.rag.schemas import RAGCitation, RAGContextResult


class LangChainRAGBackend(RAGBackend):
    def __init__(self):
        try:
            from langchain_chroma import Chroma
            from langchain_core.embeddings import Embeddings
        except ImportError as e:
            raise RuntimeError(
                "RAG_BACKEND=langchain requires optional dependencies. "
                "Install with `pip install -r requirements-langchain.txt`."
            ) from e

        embedding_engine = get_embedding_engine(settings)

        class ProjectEmbeddings(Embeddings):
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return embedding_engine.embed_documents(texts)

            def embed_query(self, text: str) -> list[float]:
                return embedding_engine.embed_query(text)

        self.vectorstore = Chroma(
            collection_name=settings.KB_COLLECTION,
            persist_directory=settings.KB_CHROMA_DIR,
            embedding_function=ProjectEmbeddings(),
            collection_metadata={"hnsw:space": "cosine"},
        )

    def build_context(self, query: str, top_k: int) -> RAGContextResult:
        if not query:
            return RAGContextResult(
                enabled=True,
                top_k=top_k,
                hits=0,
                candidate_k=0,
                context="",
                context_chars=0,
                citations=[],
                error=None,
                extra={"backend": "langchain"},
            )

        candidate_k = max(top_k, settings.KB_CANDIDATE_K)

        results = self.vectorstore.similarity_search_with_score(
            query,
            k=candidate_k,
        )

        hits: list[Hit] = []
        for idx, item in enumerate(results):
            doc, distance = item
            metadata = doc.metadata or {}

            doc_id = metadata.get("doc_id") or getattr(doc, "id", None) or f"unknown-doc-{idx}"
            chunk_id = metadata.get("chunk_id") or getattr(doc, "id", None) or f"{doc_id}:chunk-{idx}"
            source = metadata.get("source") or "unknown"
            title = metadata.get("title")

            # Chroma 的 similarity_search_with_score 返回的是距离；距离越小越相似。
            # 项目内部 Hit.score 习惯使用“越大越好”，所以这里转成近似相似度。
            try:
                score = 1.0 - float(distance)
            except Exception:
                score = 0.0

            hits.append(
                Hit(
                    doc_id=doc_id,
                    chunk_id=chunk_id,
                    score=score,
                    text=doc.page_content,
                    source=source,
                    title=title,
                )
            )

        hits = rerank_hits(query=query, hits=hits)
        hits = hits[:top_k]

        context_text, citations = build_rag_context(
            hits=hits,
            max_chars=settings.KB_MAX_CONTEXT_CHARS,
        )

        rag_citations = [
            RAGCitation(
                doc_id=c.doc_id,
                chunk_id=c.chunk_id,
                source=c.source,
                title=c.title,
            )
            for c in citations
        ]

        return RAGContextResult(
            enabled=True,
            top_k=top_k,
            hits=len(hits),
            candidate_k=candidate_k,
            context=context_text,
            context_chars=len(context_text),
            citations=rag_citations,
            error=None,
            extra={
                "backend": "langchain",
                "vectorstore": "langchain_chroma",
            },
        )