from src.app.kb.embeddings import (
    get_embedding_engine,
    reset_embedding_engine_cache,
)


class MutableSettings:
    EMBEDDING_PROVIDER = "mock"
    EMBEDDING_MODEL = "unused"
    EMBEDDING_DIM = "8"


def test_embedding_engine_is_reused_for_same_vector_space():
    reset_embedding_engine_cache()
    settings = MutableSettings()

    first = get_embedding_engine(settings)
    second = get_embedding_engine(settings)

    assert first is second
    assert first.dim == 8


def test_embedding_engine_changes_when_vector_space_config_changes():
    reset_embedding_engine_cache()
    settings = MutableSettings()

    first = get_embedding_engine(settings)
    settings.EMBEDDING_DIM = "16"
    second = get_embedding_engine(settings)

    assert second is not first
    assert second.dim == 16
