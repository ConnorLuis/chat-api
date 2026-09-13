import json

import pytest

from src.app.kb.index_contract import (
    INDEX_CONTRACT_METADATA_KEY,
    INDEX_FINGERPRINT_METADATA_KEY,
    IndexContractError,
    ensure_collection_index_contract,
)


class FakeCollection:
    def __init__(self, *, count=0, metadata=None):
        self._count = count
        self.metadata = dict(metadata or {"hnsw:space": "cosine"})

    def count(self):
        return self._count

    def modify(self, *, metadata):
        if any(
            key.startswith("hnsw:")
            for key in metadata
        ):
            raise ValueError(
                "hnsw:* collection configuration is immutable "
                "after creation"
            )
        self.metadata = dict(metadata)


class FakeSettings:
    EMBEDDING_PROVIDER = "mock"
    EMBEDDING_MODEL = "unused"
    KB_CHUNK_SIZE = 800
    KB_CHUNK_OVERLAP = 120


class FakeEngine:
    def __init__(self, dim):
        self.dim = dim


def test_empty_collection_initializes_contract():
    collection = FakeCollection(count=0)

    fingerprint = ensure_collection_index_contract(
        collection,
        settings_obj=FakeSettings(),
        embedding_engine=FakeEngine(64),
    )

    assert collection.metadata[INDEX_FINGERPRINT_METADATA_KEY] == fingerprint
    stored = json.loads(collection.metadata[INDEX_CONTRACT_METADATA_KEY])
    assert stored["embedding_provider"] == "mock"
    assert stored["embedding_dim"] == 64
    assert stored["chunk_size"] == 800


def test_non_empty_legacy_collection_is_rejected():
    collection = FakeCollection(count=3)

    with pytest.raises(IndexContractError, match="non-empty"):
        ensure_collection_index_contract(
            collection,
            settings_obj=FakeSettings(),
            embedding_engine=FakeEngine(64),
        )


def test_changed_vector_space_contract_is_rejected():
    collection = FakeCollection(count=0)
    settings = FakeSettings()

    ensure_collection_index_contract(
        collection,
        settings_obj=settings,
        embedding_engine=FakeEngine(64),
    )
    collection._count = 3

    with pytest.raises(IndexContractError, match="embedding_dim"):
        ensure_collection_index_contract(
            collection,
            settings_obj=settings,
            embedding_engine=FakeEngine(32),
        )



def test_empty_collection_can_adopt_new_contract():
    collection = FakeCollection(count=0)
    settings = FakeSettings()

    ensure_collection_index_contract(
        collection,
        settings_obj=settings,
        embedding_engine=FakeEngine(64),
    )

    fingerprint = ensure_collection_index_contract(
        collection,
        settings_obj=settings,
        embedding_engine=FakeEngine(32),
    )

    assert (
        collection.metadata[
            INDEX_FINGERPRINT_METADATA_KEY
        ]
        == fingerprint
    )

    stored = json.loads(
        collection.metadata[
            INDEX_CONTRACT_METADATA_KEY
        ]
    )
    assert stored["embedding_dim"] == 32
