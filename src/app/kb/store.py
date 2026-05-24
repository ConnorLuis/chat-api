import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.app.core.settings import settings
from src.app.kb.schemas import DocumentMeta

_io_lock = threading.Lock()

# 确保KB_DIR/docs存在
def init_storage() -> None:
    Path(settings.DOCS_DIR).mkdir(parents=True, exist_ok=True)
    index_path = Path(settings.INDEX_FILE)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    if not index_path.exists():
        index_path.write_text("", encoding="utf-8")

def save_document(title: str, text: str, source: str) -> str:
    init_storage()

    # 使用uuid生成文档id
    doc_id = str(uuid.uuid4()).replace("-", "")
    # 确定文件后，写入
    md_file_path = os.path.join(settings.DOCS_DIR, f"{doc_id}.md")
    with open(md_file_path, "w", encoding="utf-8") as f:
        f.write(text)

    now = datetime.utcnow().isoformat()

    # 构建元信息
    metadata = {
        "doc_id": doc_id,
        "title": title,
        "source": source,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": now,
        "deleted": False,
    }

    # 把元信息添加到 KB_DIR/docs.jsonl，并用_io_lock 防止并发写 jsonl 乱行
    with _io_lock:
        with open(settings.INDEX_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")

    return doc_id

def load_document(doc_id: str) -> Optional[Dict[str, Any]]:
    init_storage()

    # 按doc_id读原文
    md_path = os.path.join(settings.DOCS_DIR, f"{doc_id}.md")

    if not os.path.exists(md_path) or not os.path.exists(settings.INDEX_FILE):
        return None

    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    # 在 docs.jsonl 里找 metadata
    metadata: Optional[Dict[str, Any]] = None
    with open(settings.INDEX_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("doc_id") == doc_id:
                metadata = rec

    if not metadata:
        return None

    if metadata.get("deleted") is True:
        return None

    return {
        "doc_id": doc_id,
        "title": metadata.get("title"),
        "text": text,
        "source": metadata.get("source"),
        "created_at": metadata.get("created_at"),
        "updated_at": metadata.get("updated_at"),
        "deleted": metadata.get("deleted", False),
    }

# 核心聚合+分页函数
"""
  读取追加式 docs.jsonl，聚合文档最后状态，过滤删除，排序后分页
    :param limit: 每页条数
    :param offset: 跳过条数
    :param include_deleted: 是否包含已删除文档
    :param jsonl_path: jsonl文件路径
    :return: (文档列表, 总条数)  
"""
def list_documents(limit: int, offset: int, include_deleted: bool=False, jsonl_path: str | None = None) -> Tuple[list[DocumentMeta], int]:
    init_storage()

    if jsonl_path is None:
        jsonl_path = settings.INDEX_FILE

    # 聚合最后状态，字典存储key=doc_id, value=最新记录
    document_state: dict[str, dict] = {}

    if not os.path.exists(jsonl_path):
        return [], 0

    # 遍历jsonl文件，追加日志
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 解析json，融合坏行
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "doc_id" not in record:
                continue

            doc_id = record["doc_id"]
            if doc_id in document_state:
                # merge: keep existing fields if tombstone misses them
                merged = dict(document_state[doc_id])
                merged.update(record)
                document_state[doc_id] = merged
            else:
                document_state[doc_id] = record

    # 读取完毕，过滤
    valid_documents = []
    for record in document_state.values():
        if (not include_deleted) and record.get("deleted", False):
            continue
        valid_documents.append(record)

    # 排序，新的在最前面
    valid_documents.sort(key=lambda x: x.get("updated_at") or x.get("created_at", ""), reverse=True)

    # 进行分页
    total = len(valid_documents)
    paginated_records = valid_documents[offset: offset+limit]
    # 转换为Pydantic模型
    items = [DocumentMeta(**record) for record in paginated_records]
    return items, total

# 删除函数
"""
标记文档为删除状态：向 docs.jsonl 追加一条 tombstone 墓碑记录
    【原则】永不修改原有数据，只追加 → 安全、可审计、无并发冲突
    :param doc_id: 要删除的文档ID
    :param reason: 可选删除原因
    :return: None
"""
def mark_deleted(doc_id: str, reason: str | None = None):

    init_storage()

    tombstone_record = {
        "doc_id": doc_id,
        "deleted": True,
        "deleted_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "reason": reason
    }
    with _io_lock:
        with open(settings.INDEX_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(tombstone_record, ensure_ascii=False) + "\n")

def delete_doc_file(doc_id: str) -> bool:
    init_storage()
    doc_path = Path(settings.DOCS_DIR) / f"{doc_id}.md"

    try:
        if doc_path.exists() and doc_path.is_file():
            doc_path.unlink()
            return True
        return False
    except Exception:
        return False