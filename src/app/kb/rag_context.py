import re

from src.app.kb.schemas import Hit
from src.app.llm.schemas import Citation

VECTOR_WEIGHT = 0.7
LEXICAL_WEIGHT = 0.3
HYBRID_RETRIEVAL_MODE = "hybrid"
FUSION_METHOD = "vector_lexical"

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_:/.\-]+|[\u4e00-\u9fff]+")
_CJK_PATTERN = re.compile(r"^[\u4e00-\u9fff]+$")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "是", "的", "了", "和", "与", "或", "在", "中", "用", "用于", "这个", "那个",
    "如何", "什么", "哪些", "一个", "一种", "进行", "实现", "验证", "测试",
}

def _cjk_ngrams(token: str) -> list[str]:
    """为连续中文片段生成 2-4 gram，避免中文整句 token 无法 overlap。"""
    if len(token) <= 1:
        return []

    grams: list[str] = []
    max_n = min(4, len(token))
    for n in range(2, max_n + 1):
        for i in range(0, len(token) - n + 1):
            grams.append(token[i:i + n])
    return grams

def tokenize_query(text: str) -> list[str]:
    """轻量 tokenizer：兼容英文标识符、路径、下划线变量、中文短语。"""
    tokens: list[str] = []

    for raw in _TOKEN_PATTERN.findall((text or "").lower()):
        raw = raw.strip()
        if not raw or raw in _STOPWORDS:
            continue

        if _CJK_PATTERN.match(raw):
            tokens.extend(t for t in _cjk_ngrams(raw) if t not in _STOPWORDS)
        else:
            if len(raw) > 1:
                tokens.append(raw)

    # 去重但保持顺序，保证排序稳定
    seen = set()
    unique_tokens = []
    for tok in tokens:
        if tok not in seen:
            seen.add(tok)
            unique_tokens.append(tok)

    return unique_tokens

def _token_set(text: str) -> set[str]:
    return set(tokenize_query(text))


def _normalize_vector_score(score: float) -> float:
    """项目内部 score 约定越大越好；这里做保守 clamp，避免异常值压坏 fusion。"""
    try:
        value = float(score)
    except (TypeError, ValueError):
        return 0.0

    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value

def lexical_score(query: str, hit: Hit) -> float:
    """
    计算词面匹配分数，范围大致控制在 0-1。
    设计原则：
    - title 命中最重要；
    - text 命中次之；
    - source 命中只给少量加分；
    - exact phrase 给轻量 bonus；
    - 不用全局主题无条件加分，避免 Day19 曾遇到的 rerank 过拟合。
    """
    q = (query or "").lower().strip()
    if not q:
        return 0.0

    query_tokens = set(tokenize_query(q))
    if not query_tokens:
        return 0.0

    title = (hit.title or "").lower()
    source = (hit.source or "").lower()
    text = (hit.text or "").lower()

    title_tokens = _token_set(title)
    source_tokens = _token_set(source)
    text_tokens = _token_set(text)

    title_overlap = query_tokens & title_tokens
    source_overlap = query_tokens & source_tokens
    text_overlap = query_tokens & text_tokens

    score = 0.0

    # exact phrase：只给轻量 bonus，防止整句重复直接压过所有规则
    if q and title and q in title:
        score += 0.35
    if q and text and q in text:
        score += 0.20

    # token overlap：title > text > source
    score += min(0.35, 0.08 * len(title_overlap))
    score += min(0.35, 0.04 * len(text_overlap))
    score += min(0.15, 0.03 * len(source_overlap))

    return min(1.0, score)

def _rule_bonus(query: str, hit: Hit) -> float:
    """
    保留 Day19/Day20 已验证过的 query-aware 专题规则。
    注意：这些规则必须由 query 触发，不能无条件按文档主题加分。
    """
    q = (query or "").lower()
    text = (hit.text or "").lower()
    title = (hit.title or "").lower()

    bonus_score = 0.0

    strong_terms = [
        "candidate_k",
        "rerank",
        "top_k",
        "候选池",
        "重排",
        "精排",
    ]

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
            "query_terms": ["tmp_path", "monkeypatch", "kb_dir", "kb_chroma_dir", "run_log_path", "契约测试", "隔离"],
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

    # 3. 显式工程 token 出现在正文，给轻量加分
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

def fusion_score(query: str, hit: Hit) -> float:
    """
    Hybrid score:
    - vector score：语义召回分；
    - lexical score：词面命中分；
    - rule bonus：已验证过的 query-aware 专题规则。
    """
    vector_part = VECTOR_WEIGHT * _normalize_vector_score(hit.score)
    lexical_part = LEXICAL_WEIGHT * lexical_score(query, hit)
    rule_part = _rule_bonus(query, hit)

    return vector_part + lexical_part + rule_part


def rerank_hits(query: str, hits: list[Hit]) -> list[Hit]:
    """
    Hybrid rerank：vector retrieval + lexical signal + query-aware rule bonus。
    """
    if not hits:
        return []

    return sorted(
        hits,
        key=lambda hit: (
            fusion_score(query, hit),
            _normalize_vector_score(hit.score),
            hit.doc_id,
            hit.chunk_id,
        ),
        reverse=True,
    )

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
            context_parts.append(chunk_content)
            citations.append(Citation(
                doc_id=hit.doc_id,
                chunk_id=hit.chunk_id,
                source=hit.source,
                title=hit.title
            ))
            total_length += content_length
        else:
            remaining = max_chars - total_length
            if remaining > 0:
                truncated_content = chunk_content[:remaining]
                context_parts.append(truncated_content)
                citations.append(Citation(
                    doc_id=hit.doc_id,
                    chunk_id=hit.chunk_id,
                    source=hit.source,
                    title=hit.title
                ))
            break

    final_context = "".join(context_parts)
    return final_context, citations