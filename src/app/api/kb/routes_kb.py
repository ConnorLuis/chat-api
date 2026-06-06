import time
import uuid

from fastapi import Path as ApiPath
from fastapi import APIRouter, Query, HTTPException, Request

from src.app.kb import store, chunking
from src.app.kb.chroma_store import get_collection, delete_doc, query, upsert_chunks
from src.app.kb.embeddings import get_embedding_engine
from src.app.core.settings import settings
from src.app.kb.index_text import extract_index_text
from src.app.kb.schemas import DocumentResponse, DocumentRequest, SearchResponse, Hit, DocumentsListResponse, \
    DeleteDocumentResponse
from src.app.kb.store import delete_doc_file, mark_deleted

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
    doc_id = store.save_document(
        title=request.title or "Untitled",
        text=request.text,
        source=request.source
    )
    # 切分文本成块
    raw_text = request.text
    index_text = extract_index_text(raw_text=raw_text)
    chunks_data = chunking.split_text(index_text, settings.KB_CHUNK_SIZE, settings.KB_CHUNK_OVERLAP)
    if not chunks_data:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return DocumentResponse(doc_id=doc_id,chunks = 0, metadata = {"trace_id": trace_id, "latency_ms": latency_ms})
    chunks_texts = [c.text for c in chunks_data]
    # 获取向量数据库的collection
    collection = get_collection(settings.KB_CHROMA_DIR, settings.KB_COLLECTION, space="cosine")


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
    upsert_chunks(collection=collection, doc_id=doc_id, chunks=chunks_texts, embeddings=embeddings, metadatas=chroma_metadatas)

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

    collection = get_collection(settings.KB_CHROMA_DIR, settings.KB_COLLECTION, space="cosine")
    engine = get_engine()
    query_vector = engine.embed_query(q)
    hits_raw = query(collection, query_vector, top_k=top_k)
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

@router.get("/documents", response_model=DocumentsListResponse)
async def show_documents(http_request: Request, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), include_deleted: bool = Query(False)):
    start_time = time.perf_counter()
    trace_id = getattr(http_request.state, "trace_id", None) or http_request.headers.get("x-trace-id") or f"tr-{uuid_like_string()}"

    items, total = store.list_documents(limit=limit,offset=offset, include_deleted=include_deleted, jsonl_path=settings.INDEX_FILE,)
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    return DocumentsListResponse(items=items, total=total, metadata={"trace_id": trace_id, "latency_ms": latency_ms})

@router.delete("/documents/{doc_id}", response_model=DeleteDocumentResponse)
def delete_document(http_request: Request, doc_id: str = ApiPath(..., description="文档唯一ID"), reason: str | None = Query(None)):

    start_time = time.perf_counter()
    trace_id = (
            getattr(http_request.state, "trace_id", None)
            or http_request.headers.get("x-trace-id")
            or f"tr-{uuid_like_string()}"
    )

    doc = store.load_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"文档{doc_id} 不存在")
    # 开始删除逻辑
    # 获取向量库集合
    collection = get_collection(settings.KB_CHROMA_DIR, settings.KB_COLLECTION, space="cosine")
    # 删除向量数据
    deleted_vectors = delete_doc(collection, doc_id)
    # 删除本地文件
    deleted_file = delete_doc_file(doc_id)
    mark_deleted(doc_id, reason=reason)
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    # 响应返回
    return DeleteDocumentResponse(doc_id=doc_id, deleted=True, metadata={"trace_id": trace_id, "latency_ms": latency_ms, "deleted_vectors": deleted_vectors, "deleted_file": deleted_file, "marked_deleted": True})
