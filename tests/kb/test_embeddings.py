import sys
from types import SimpleNamespace

from src.app.kb.embeddings import HFEmbeddingEngine


class _FakeArray:
    def __init__(self, value):
        self.value = value

    def tolist(self):
        return self.value


class _FakeSentenceTransformer:
    def __init__(self, model_name_or_path: str):
        self.model_name_or_path = model_name_or_path
        self.calls = []

    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, texts, **kwargs):
        self.calls.append((texts, kwargs))

        if isinstance(texts, list):
            return _FakeArray([[1.0, 0.0, 0.0] for _ in texts])

        return _FakeArray([0.0, 1.0, 0.0])


def test_hf_embedding_engine_uses_model_name_and_dimension(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer),
    )

    engine = HFEmbeddingEngine(
        model_name_or_path="organization/model-name"
    )

    assert engine.model.model_name_or_path == "organization/model-name"
    assert engine.dim == 3
    assert engine.embed_documents(["a", "b"]) == [
        [1.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
    ]
    assert engine.embed_query("query") == [0.0, 1.0, 0.0]


def test_hf_embedding_engine_returns_zero_vector_for_empty_query(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer),
    )

    engine = HFEmbeddingEngine(model_name_or_path="organization/model-name")

    assert engine.embed_query("") == [0.0, 0.0, 0.0]
