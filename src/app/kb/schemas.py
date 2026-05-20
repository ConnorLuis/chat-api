from pydantic import Field
from typing import Optional, Dict, Any, List

from pydantic import BaseModel


# 入库请求
class DocumentRequest(BaseModel):
    text: str = Field(..., description="原始文档完整文本")
    title: Optional[str] = Field(None, description="文档标题")
    source: str = Field("manual", description="文档来源")

# 入库响应
class DocumentResponse(BaseModel):
    doc_id: str
    chunks: int
    metadata: Dict[str, Any] = Field(default_factory=dict)

# 一次检索命中
class Hit(BaseModel):
    doc_id: str
    chunk_id: str
    score: float
    text: str
    source: str
    title: Optional[str] = None

# 检索响应
class SearchResponse(BaseModel):
    query: str
    top_k: int
    hits: List[Hit]
    metadata: Dict[str, Any] = Field(default_factory=dict)

# 内部分块结构
class Chunk(BaseModel):
    chunk_id: str
    text: str
    start: int
    end: int
    idx: int
