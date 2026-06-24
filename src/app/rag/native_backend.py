import time

from src.app.core.settings import settings
from src.app.kb import chroma_store
from src.app.kb.embeddings import get_embedding_engine
from src.app.kb.rag_context import build_rag_context, rerank_hits
from src.app.kb.schemas import Hit
from src.app.rag.base import RAGBackend
from src.app.rag.schemas import RAGCitation, RAGContextResult


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


class NativeRAGBackend(RAGBackend):
    def build_context(self, query: str, top_k: int) -> RAGContextResult:
        total_start = time.perf_counter()

        timing = {
            "backend": "native",
            "embedding_ms": 0,
            "retrieval_ms": 0,
            "rerank_ms": 0,
            "context_build_ms": 0,
            "total_ms": 0,
        }

        if not query:
            timing["total_ms"] = _ms(total_start)
            return RAGContextResult(
                enabled=True,
                top_k=top_k,
                hits=0,
                candidate_k=0,
                context="",
                context_chars=0,
                citations=[],
                error=None,
                extra=timing,
            )

        candidate_k = max(top_k, settings.KB_CANDIDATE_K)

        collection = chroma_store.get_collection(settings.KB_CHROMA_DIR, settings.KB_COLLECTION)
        embed_engine = get_embedding_engine(settings)

        t0 = time.perf_counter()
        query_vector = embed_engine.embed_query(query)
        timing["embedding_ms"] = _ms(t0)

        t0 = time.perf_counter()
        hits_raw = chroma_store.query(collection, query_vector, top_k=candidate_k)
        timing["retrieval_ms"] = _ms(t0)

        hits: list[Hit] = []
        for h in hits_raw:
            metadata = h.get("metadata") or {}
            hits.append(Hit(
                doc_id=metadata["doc_id"],
                chunk_id=metadata.get("chunk_id", h["id"]),
                score=h["score"],
                text=h["text"],
                source=metadata["source"],
                title=metadata.get("title")
            ))

        t0 = time.perf_counter()
        hits = rerank_hits(query=query, hits=hits)
        hits = hits[:top_k]
        timing["rerank_ms"] = _ms(t0)

        t0 = time.perf_counter()
        context_text, citations = build_rag_context(hits=hits, max_chars=settings.KB_MAX_CONTEXT_CHARS)
        timing["context_build_ms"] = _ms(t0)

        rag_citations = [
            RAGCitation(
                doc_id=c.doc_id,
                chunk_id=c.chunk_id,
                source=c.source,
                title=c.title,
            )
            for c in citations
        ]

        timing["total_ms"] = _ms(total_start)

        return RAGContextResult(
            enabled=True,
            top_k=top_k,
            hits=len(hits),
            candidate_k=candidate_k,
            context=context_text,
            context_chars=len(context_text),
            citations=rag_citations,
            error=None,
            extra=timing
        )