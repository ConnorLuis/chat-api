import threading
from typing import Dict, List, Any, Optional

import chromadb
from chromadb.api.models.Collection import Collection

_client_cache: Dict[str, chromadb.PersistentClient] = {}
_cache_lock = threading.Lock()

def get_collection(persist_dir: str, collection_name: str, space: str="cosine") -> Collection:
    global _client_cache

    # 用 _client_cache 按 persist_dir 缓存 PersistentClient，避免每次请求都重新打开数据库（更快也更稳）
    if persist_dir not in _client_cache:
        with _cache_lock:
            if persist_dir not in _client_cache:
                _client_cache[persist_dir] = chromadb.PersistentClient(path=persist_dir)

    client = _client_cache[persist_dir]

    # get_or_create_collection(name=..., metadata={"hnsw:space": space})：设置向量空间度量方式
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": space}
    )

    return collection

def upsert_chunks(collection: Collection, doc_id: str, chunks: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]]) -> None:
    if not (len(chunks) == len(embeddings) == len(metadatas)):
        raise ValueError(
            f"长度不匹配：chunks({len(chunks)}), "
            f"embeddings({len(embeddings)}), metadatas({len(metadatas)}) 必须保持一致。"
        )

    if not chunks:
        return

    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]

    collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)


def query(collection: Collection, query_embedding: List[float], top_k: int=5, where: Optional[Dict[str,Any]] = None) -> List[Dict[str, Any]]:
    raw_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"]
    )

    if not raw_results or not raw_results["ids"] or not raw_results["ids"][0]:
        return []

    ids = raw_results["ids"][0]
    distances = raw_results["distances"][0] if raw_results["distances"] else [1.0] * len(ids)
    documents = raw_results["documents"][0] if raw_results["documents"] else [""] * len(ids)
    metadatas = raw_results["metadatas"][0] if raw_results["metadatas"] else [{}] * len(ids)

    coll_metadata = collection.metadata or {}
    space_type = coll_metadata.get("hnsw:space", "cosine")

    hits =[]
    for idx in range(len(ids)):
        distance = distances[idx]

        if space_type == "cosine":
            score = 1.0 - distance
        elif space_type ==  "l2":
            score = 1.0 / (1.0 + distance)
        elif space_type == "ip":
            score = 1.0 -distance
        else:
            score = 1.0 - distance

        hits.append({
            "id": ids[idx],
            "text": documents[idx],
            "metadata": metadatas[idx],
            "score": round(float(score), 4)
        })

    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits

def delete(collection: Collection, doc_id: Optional[str] = None, chunk_ids: Optional[List[str]] = None) -> None:
    if chunk_ids:
        collection.delete(ids = chunk_ids)
        return
    if doc_id:
        collection.delete(where={"doc_id": doc_id})
        return

def delete_doc(collection: Collection, doc_id: Optional[str] = None) -> int:
    if doc_id:
        count = len(collection.get(where={"doc_id": doc_id})["ids"])
        collection.delete(where={"doc_id": doc_id})
        return count
    return 0