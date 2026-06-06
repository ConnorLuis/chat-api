from types import SimpleNamespace

from src.app.kb.rag_context import rerank_hits


def make_hit(title: str, text: str, score: float = 0.8):
    return SimpleNamespace(
        doc_id=title.lower().replace(" ", "-"),
        chunk_id=title.lower().replace(" ", "-") + "_chunk_0",
        source="kb_seed",
        title=title,
        text=text,
        score=score,
    )


def test_candidate_k_query_promotes_rag_candidate_pool_chunk():
    rag_hit = make_hit(
        title="RAG in Chat/Stream",
        text="candidate_k 是候选池大小，rerank 负责重排，top_k 是最终注入数量。",
        score=0.70,
    )
    generic_hit = make_hit(
        title="KB Documents Management",
        text="docs.jsonl 是 append-only 索引日志，delete 会写 tombstone。",
        score=0.90,
    )

    ranked = rerank_hits(
        query="candidate_k 在 RAG 中用来做什么？为什么 top_k 可以小但 candidate_k 可以更大？",
        hits=[generic_hit, rag_hit],
    )

    assert ranked[0].title == "RAG in Chat/Stream"


def test_docs_jsonl_query_does_not_unconditionally_promote_rag_document():
    rag_hit = make_hit(
        title="RAG in Chat/Stream",
        text="candidate_k 是候选池大小，rerank 负责重排，top_k 是最终注入数量。",
        score=0.88,
    )
    kb_hit = make_hit(
        title="KB Ingest & Search",
        text="docs.jsonl 保存文档索引元数据，save_document 会落盘 md 并追加 create 记录。",
        score=0.80,
    )

    ranked = rerank_hits(
        query="项目中 docs.jsonl 的作用是什么？",
        hits=[rag_hit, kb_hit],
    )

    assert ranked[0].title == "KB Ingest & Search"


def test_sse_query_promotes_stream_sse_protocol_not_rag():
    sse_hit = make_hit(
        title="Stream SSE Protocol",
        text="SSE block 使用 event: 和 data: 字段，并用空行分隔；data 支持多行。",
        score=0.75,
    )
    rag_hit = make_hit(
        title="RAG in Chat/Stream",
        text="RAG context injection 返回 citations 和 top_k 摘要。",
        score=0.86,
    )

    ranked = rerank_hits(
        query="SSE 的事件块 block 格式是什么？为什么必须用空行分隔？data 支持多行吗？",
        hits=[rag_hit, sse_hit],
    )

    assert ranked[0].title == "Stream SSE Protocol"


def test_environment_query_promotes_environment_ops():
    env_hit = make_hit(
        title="Environment & Ops",
        text="WSL 通过 /mnt/c/Users/<user>/models/bce-embedding-base_v1 加载 Windows 本地模型。",
        score=0.70,
    )
    rag_hit = make_hit(
        title="RAG in Chat/Stream",
        text="candidate_k、rerank、top_k 用于 RAG 检索排序。",
        score=0.90,
    )

    ranked = rerank_hits(
        query="WSL 中如何加载 Windows 本地的 bce-embedding-base_v1 模型？",
        hits=[rag_hit, env_hit],
    )

    assert ranked[0].title == "Environment & Ops"