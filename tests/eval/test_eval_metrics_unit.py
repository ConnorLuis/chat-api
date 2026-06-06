from scripts.eval_qa_rag import score_answer, score_citations


def test_score_answer_passes_when_keywords_reach_min_hits():
    score = score_answer(
        answer="candidate_k 用于扩大候选池，top_k 控制最终注入上下文数量。",
        expected_keywords=["candidate_k", "top_k", "候选池"],
        min_hits=2,
    )

    assert score["hits_count"] >= 2
    assert score["uncertain"] is False
    assert score["answer_hit"] is True


def test_score_answer_uncertain_answer_must_not_pass_even_with_keywords():
    score = score_answer(
        answer="不确定/需要更多上下文。文档中没有提供 candidate_k 和 top_k 的具体解释。",
        expected_keywords=["candidate_k", "top_k"],
        min_hits=2,
    )

    assert score["hits_count"] == 2
    assert score["uncertain"] is True
    assert score["answer_hit"] is False


def test_score_answer_does_not_treat_valid_not_found_semantics_as_uncertain():
    score = score_answer(
        answer="trace_id 是精确查询键；如果记录不存在，语义上就是 not found，因此返回 404。",
        expected_keywords=["trace_id", "404", "不存在", "语义"],
        min_hits=2,
    )

    assert score["uncertain"] is False
    assert score["answer_hit"] is True


def test_score_citations_source_hit_is_hard_gate_title_hit_is_diagnostic():
    citations = [
        {
            "doc_id": "doc-1",
            "chunk_id": "doc-1_chunk_0",
            "source": "kb_seed",
            "title": "Some Other Title",
        }
    ]

    score = score_citations(
        citations=citations,
        expected_sources=["kb_seed"],
        expected_titles=["RAG in Chat/Stream"],
    )

    assert score["has_citations"] is True
    assert score["source_hit"] is True
    assert score["title_hit"] is False
    assert score["citation_hit"] is True


def test_score_citations_title_hit_when_expected_title_present():
    citations = [
        {
            "doc_id": "doc-2",
            "chunk_id": "doc-2_chunk_1",
            "source": "kb_seed",
            "title": "RAG in Chat/Stream",
        }
    ]

    score = score_citations(
        citations=citations,
        expected_sources=["kb_seed"],
        expected_titles=["RAG in Chat/Stream"],
    )

    assert score["citation_hit"] is True
    assert score["title_hit"] is True
    assert score["matched_titles"] == ["RAG in Chat/Stream"]