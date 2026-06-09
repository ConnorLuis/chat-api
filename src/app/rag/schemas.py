from typing import Any

from pydantic import BaseModel, Field

class RAGCitation(BaseModel):
    doc_id: str
    chunk_id: str
    source: str | None = None
    title: str | None = None


class RAGContextResult(BaseModel):
    enabled: bool
    top_k: int
    hits: int
    candidate_k: int
    context: str
    context_chars: int
    citations: list[RAGCitation]
    error: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
