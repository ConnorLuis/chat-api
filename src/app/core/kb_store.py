import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from src.app.core.settings import settings

_io_lock = threading.Lock()

# 确保KB_DIR/docs存在
def init_storage() -> None:
    if not os.path.exists(settings.DOCS_DIR):
        os.makedirs(settings.DOCS_DIR, exist_ok=True)

def save_document(title: str, text: str, source: str) -> str:
    init_storage()

    # 使用uuid生成文档id
    doc_id = str(uuid.uuid4()).replace("-", "")
    # 确定文件后，写入
    md_file_path = os.path.join(settings.DOCS_DIR, f"{doc_id}.md")
    with open(md_file_path, "w", encoding="utf-8") as f:
        f.write(text)

    # 构建元信息
    metadata = {
        "doc_id": doc_id,
        "title": title,
        "source": source,
        "created_at": datetime.utcnow().isoformat()
    }

    # 把元信息添加到 KB_DIR/docs.jsonl，并用_io_lock 防止并发写 jsonl 乱行
    with _io_lock:
        with open(settings.INDEX_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")

    return doc_id

def load_document(doc_id: str) -> Optional[Dict[str, Any]]:
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
            data = json.loads(line)
            if data.get("doc_id") == doc_id:
                metadata = data
                break
    if not metadata:
        return None

    return {
        "doc_id": metadata["doc_id"],
        "title": metadata["title"],
        "text": text,
        "source": metadata["source"],
        "created_at": metadata["created_at"]
    }