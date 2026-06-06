import re

from src.app.kb.schemas import Hit
from src.app.llm.schemas import Citation

def rerank_hits(query: str, hits:list[Hit]) -> list[Hit]:
    """
    对检索命中的结果进行规则化重排序
    :param query: 用户查询语句
    :param hits: 原始向量检索命中结果列表
    :return: 重排序后的命中结果列表
    """
    if not hits:
        return []

    q = query.lower()

    strong_terms = [
        "candidate_k",
        "rerank",
        "top_k",
        "候选池",
        "重排",
        "精排",
    ]

    def calculate_bonus(hit: Hit) -> float:
        text = (hit.text or "").lower()
        title = (hit.title or "").lower()
        bonus_score = 0.0

        # 1. 只有 query 里真的出现强术语，才按强术语加分
        for term in strong_terms:
            term_lower = term.lower()
            if term_lower in q and term_lower in text:
                bonus_score += 3.0

        # 2. 专题级 title boost：必须由 query 触发，不能无条件加
        topic_rules = [
            {
                "query_terms": ["docs.jsonl", "save_document", "split_text", "chunk_size", "overlap", "next_start",
                                "mockembeddingengine", "upsert_chunks", "extract_index_text", "score", "cosine",
                                "hnsw:space", "normalize"],
                "title": "kb ingest & search",
                "bonus": 4.0,
            },
            {
                "query_terms": ["/kb/documents", "delete", "tombstone", "删除", "软删除"],
                "title": "kb documents management",
                "bonus": 4.0,
            },
            {
                "query_terms": ["tmp_path", "monkeypatch", "kb_dir", "kb_chroma_dir", "run_log_path", "契约测试",
                                "隔离"],
                "title": "testing strategy",
                "bonus": 4.0,
            },
            {
                "query_terms": ["bce-embedding-base_v1", "/mnt/c", "wsl", "windows", "本地模型"],
                "title": "environment & ops",
                "bonus": 4.0,
            },
            {
                "query_terms": ["sse", "event:", "data:", "block", "空行", "/chat/stream", "error event"],
                "title": "stream sse protocol",
                "bonus": 4.0,
            },
            {
                "query_terms": ["/chat", "502", "bad gateway", "http 200", "下游失败"],
                "title": "chat api contract",
                "bonus": 3.0,
            },
            {
                "query_terms": ["prompthub", "prompt_id", "prompt_version", "prompt_vars", "system prompt"],
                "title": "prompthub",
                "bonus": 4.0,
            },
            {
                "query_terms": ["compare_group_id", "a/b", "compare", "回放", "聚合"],
                "title": "a/b compare",
                "bonus": 4.0,
            },
            {
                "query_terms": ["runs.jsonl", "/runs/trace", "trace_id", "404", "run 记录", "审计"],
                "title": "run logs & replay",
                "bonus": 4.0,
            },
            {
                "query_terms": ["candidate_k", "rerank", "top_k", "候选池", "重排", "精排"],
                "title": "rag in chat/stream",
                "bonus": 4.0,
            },
        ]

        for rule in topic_rules:
            if any(t in q for t in rule["query_terms"]) and rule["title"] in title:
                bonus_score += rule["bonus"]

        # 3. query 里的显式词如果出现在正文，给轻量加分
        # 注意：这是轻量，不要压过专题 title boost
        query_tokens = [
            "docs.jsonl", "split_text", "chunk_size", "overlap", "next_start",
            "mockembeddingengine", "upsert_chunks", "extract_index_text",
            "candidate_k", "rerank", "top_k",
            "tmp_path", "monkeypatch", "kb_dir", "kb_chroma_dir", "run_log_path",
            "bce-embedding-base_v1", "/mnt/c",
            "prompt_id", "prompt_version", "prompt_vars",
            "compare_group_id", "runs.jsonl", "trace_id",
            "score", "cosine", "hnsw:space", "normalize",
        ]

        for tok in query_tokens:
            if tok in q and tok in text:
                bonus_score += 1.5

        return bonus_score

    # 排序：原始向量分数 + 自定义加分 降序排列
    sorted_hits = sorted(
        hits,
        key=lambda hit: (hit.score + calculate_bonus(hit)),  # 核心：原始分 + 加分
        reverse=True
    )

    return sorted_hits

# 构建RAG上下文 + 生成引用列表
def build_rag_context(hits: list[Hit], max_chars: int = 3000) -> tuple[str, list[Citation]]:
    """
    拼接RAG检索结果为上下文文本，并生成引用列表
    :param hit: 检索命中结果列表，每个元素包含内容文本，文档元数据
    :param max_chars: 最大字符长度，防止prompt过长
    :return: 拼接后的上下文文本，引用列表
    """
    if not hits:
        return "", []

    context_parts = []
    citations = []
    total_length = 0

    for idx, hit in enumerate(hits, start=1):
        chunk_text = hit.text
        citation_header = f"[{idx}] (doc_id={hit.doc_id}, chunk_id={hit.chunk_id}, source={hit.source}, title={hit.title})"
        chunk_content = f"{citation_header}\n{chunk_text}\n"
        content_length = len(chunk_content)

        if total_length + content_length <= max_chars:
            # 完整加入：文本 + 引用
            context_parts.append(chunk_content)
            citations.append(Citation(
                doc_id=hit.doc_id,
                chunk_id=hit.chunk_id,
                source=hit.source,
                title=hit.title
            ))
            total_length += content_length
        else:
            # 无法完整加入：计算可容纳的截断长度
            remaining = max_chars - total_length
            if remaining > 0:
                # 截断后仍有内容：必须追加 文本 + 引用
                truncated_content = chunk_content[:remaining]
                context_parts.append(truncated_content)
                citations.append(Citation(
                    doc_id=hit.doc_id,
                    chunk_id=hit.chunk_id,
                    source=hit.source,
                    title=hit.title
                ))
            # 超出最大长度，终止循环
            break

    final_context = "".join(context_parts)
    return final_context, citations

