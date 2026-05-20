import time
import uuid
from fastapi import APIRouter, Query, HTTPException, Request

from src.app.core import kb_store, kb_chunking, kb_chroma_store
from src.app.core.kb_embeddings import get_embedding_engine
from src.app.core.settings import settings
from src.app.kb.schemas import DocumentResponse, DocumentRequest, SearchResponse, Hit

router = APIRouter(prefix="/kb")

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = get_embedding_engine(settings)
    return _engine

def uuid_like_string():
    return str(uuid.uuid4())[:8]

"""
POST /kb/documents
请求体（建议最小）：
    title: str（可空）
    text: str（必填）
    source: str（默认 "manual"）
响应体：
    doc_id: str
    chunks: int
"""
@router.post("/documents", response_model=DocumentResponse)
async def create_document(request: DocumentRequest, http_request: Request):
    start_time = time.perf_counter()
    trace_id = getattr(http_request.state, "trace_id", None) or http_request.headers.get("x-trace-id") or f"tr-{uuid_like_string()}"
    # 保存原文
    # 内部会自动创建本地目录，并向docs.jsonl追加元数据
    doc_id = kb_store.save_document(
        title=request.title or "Untitled",
        text=request.text,
        source=request.source
    )
    # 切分文本成块
    chunks_data = kb_chunking.split_text(request.text, settings.KB_CHUNK_SIZE, settings.KB_CHUNK_OVERLAP)
    chunks_texts = [c.text for c in chunks_data]
    # 获取向量数据库的collection
    collection = kb_chroma_store.get_collection(settings.KB_CHROMA_DIR, settings.KB_COLLECTION, space="cosine")


    # 向量化chunk，批量计算所有chunk的向量
    engine = get_engine()
    embeddings = engine.embed_documents(chunks_texts)

    # chroma upsert（结构化构造）
    chroma_metadatas = []

    for c in chunks_data:
        meta = {
            "doc_id": doc_id,
            "chunk_index": c.idx,
            "chunk_id": f"{doc_id}_chunk_{c.idx}",
            "source": request.source,
            "start": c.start,
            "end": c.end
        }

        if request.title:
            meta["title"] = request.title

        chroma_metadatas.append(meta)
    # 更新到chroma库
    kb_chroma_store.upsert_chunks(collection=collection, doc_id=doc_id, chunks=chunks_texts, embeddings=embeddings, metadatas=chroma_metadatas)

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    return DocumentResponse(doc_id=doc_id,
                            chunks = len(chunks_data),
                            metadata = {
                                "trace_id": trace_id,
                                "latency_ms": latency_ms
                            })
"""
GET /kb/search

参数：
    q: str
    top_k: int = 5
响应体：
    query
    top_k
    hits: list[Hit]
    doc_id
    chunk_id
    score
    text
    source
    （可选）title
"""
@router.get("/search", response_model=SearchResponse)
async def search_knowledge_base(
        http_request: Request,
        q: str = Query(..., description="检索关键词"),
        top_k: int = Query(settings.KB_TOP_K, description="返回前 K 个最相似的结果")
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty")
    start_time = time.perf_counter()
    trace_id = getattr(http_request.state, "trace_id", None) or http_request.headers.get(
        "x-trace-id") or f"tr-{uuid_like_string()}"

    collection = kb_chroma_store.get_collection(settings.KB_CHROMA_DIR, settings.KB_COLLECTION, space="cosine")
    engine = get_engine()
    query_vector = engine.embed_query(q)
    hits_raw = kb_chroma_store.query(collection, query_vector, top_k=top_k)
    hits = []
    for h in hits_raw:
        doc_id =  h["metadata"]["doc_id"]
        chunk_id= h["metadata"].get("chunk_id", h["id"])
        score= h["score"]
        text= h["text"]
        source= h["metadata"]["source"]
        title= h["metadata"].get("title")
        hit = Hit(doc_id=doc_id, chunk_id=chunk_id, score=score, text=text, source=source, title=title)
        hits.append(hit)
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    return SearchResponse(query=q, top_k=top_k, hits=hits, metadata={"trace_id": trace_id, "latency_ms": latency_ms})
