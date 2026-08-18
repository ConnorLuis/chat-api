from src.app.kb.rag_context import (
    FUSION_METHOD,
    HYBRID_RETRIEVAL_MODE,
    LEXICAL_WEIGHT,
    VECTOR_WEIGHT,
    fusion_score,
    lexical_score,
    rerank_hits,
)
from src.app.kb.schemas import Hit


def make_hit(
    *,
    doc_id: str,
    chunk_id: str,
    score: float,
    text: str,
    title: str | None = None,
    source: str = "test",
) -> Hit:
    return Hit(
        doc_id=doc_id,
        chunk_id=chunk_id,
        score=score,
        text=text,
        source=source,
        title=title,
    )


def test_hybrid_constants_are_stable():
    assert HYBRID_RETRIEVAL_MODE == "hybrid"
    assert FUSION_METHOD == "vector_lexical"
    assert VECTOR_WEIGHT == 0.7
    assert LEXICAL_WEIGHT == 0.3


def test_lexical_score_prefers_exact_title_and_text_match():
    query = "target_token_alpha 如何配置"

    weak = make_hit(
        doc_id="weak",
        chunk_id="c1",
        score=0.99,
        title="Generic Document",
        text="This chunk talks about something unrelated.",
    )
    strong = make_hit(
        doc_id="strong",
        chunk_id="c2",
        score=0.10,
        title="target_token_alpha Configuration",
        text="target_token_alpha is used to verify lexical matching.",
    )

    assert lexical_score(query, strong) > lexical_score(query, weak)


def test_hybrid_rerank_can_promote_strong_lexical_match():
    query = "target_token_alpha 如何配置"

    vector_only = make_hit(
        doc_id="vector",
        chunk_id="c1",
        score=0.70,
        title="Generic Vector Match",
        text="This text is semantically close but does not contain the target keyword.",
    )
    lexical_match = make_hit(
        doc_id="lexical",
        chunk_id="c2",
        score=0.68,
        title="target_token_alpha Configuration",
        text="target_token_alpha is the exact keyword that should be preferred.",
    )

    ranked = rerank_hits(query, [vector_only, lexical_match])

    assert ranked[0].doc_id == "lexical"
    assert ranked[1].doc_id == "vector"


def test_hybrid_rerank_keeps_all_hits_and_is_deterministic():
    query = "candidate_k rerank top_k"

    hits = [
        make_hit(
            doc_id="b",
            chunk_id="2",
            score=0.40,
            title="Other",
            text="unrelated text",
        ),
        make_hit(
            doc_id="a",
            chunk_id="1",
            score=0.40,
            title="Other",
            text="unrelated text",
        ),
    ]

    ranked = rerank_hits(query, hits)

    assert len(ranked) == len(hits)
    assert {h.doc_id for h in ranked} == {"a", "b"}

    ranked_again = rerank_hits(query, hits)
    assert [h.doc_id for h in ranked] == [h.doc_id for h in ranked_again]


def test_fusion_score_is_not_lower_than_vector_component_for_valid_score():
    hit = make_hit(
        doc_id="x",
        chunk_id="1",
        score=0.5,
        title="target_token_alpha",
        text="target_token_alpha appears here.",
    )

    assert fusion_score("target_token_alpha", hit) >= VECTOR_WEIGHT * 0.5