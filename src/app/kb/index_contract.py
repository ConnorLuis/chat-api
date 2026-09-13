from __future__ import annotations

import hashlib
import json
from typing import Any


INDEX_CONTRACT_VERSION = 1
INDEX_CONTRACT_METADATA_KEY = "chat_api_index_contract"
INDEX_FINGERPRINT_METADATA_KEY = "chat_api_index_fingerprint"


class IndexContractError(RuntimeError):
    """Persistent vector index does not match the active runtime contract."""


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def index_contract_fingerprint(
    contract: dict[str, Any],
) -> str:
    raw = _canonical_json(contract).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _metadata_for_modify(
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Remove Chroma creation-only HNSW fields before modify().

    hnsw:* values configure the physical collection and cannot be
    changed through Collection.modify() after creation.
    """

    return {
        key: value
        for key, value in metadata.items()
        if not key.startswith("hnsw:")
    }


def build_index_contract(
    settings_obj: Any,
    embedding_engine: Any,
    *,
    space: str = "cosine",
) -> dict[str, Any]:
    provider = (
        settings_obj
        .EMBEDDING_PROVIDER
        .strip()
        .lower()
    )

    model = (
        settings_obj.EMBEDDING_MODEL.strip()
        if provider == "hf"
        else "mock-hash-sha256-v1"
    )

    return {
        "version": INDEX_CONTRACT_VERSION,
        "distance_space": space,
        "embedding_provider": provider,
        "embedding_model": model,
        "embedding_dim": int(
            embedding_engine.dim
        ),
        "chunk_size": int(
            settings_obj.KB_CHUNK_SIZE
        ),
        "chunk_overlap": int(
            settings_obj.KB_CHUNK_OVERLAP
        ),
    }


def _persist_contract(
    collection: Any,
    *,
    current_metadata: dict[str, Any],
    contract_json: str,
    fingerprint: str,
) -> None:
    metadata = _metadata_for_modify(
        current_metadata
    )

    metadata[
        INDEX_CONTRACT_METADATA_KEY
    ] = contract_json

    metadata[
        INDEX_FINGERPRINT_METADATA_KEY
    ] = fingerprint

    collection.modify(
        metadata=metadata
    )


def ensure_collection_index_contract(
    collection: Any,
    *,
    settings_obj: Any,
    embedding_engine: Any,
    space: str = "cosine",
) -> str:
    """Initialize or validate the persistent-vector-index contract.

    An empty collection may adopt the active runtime contract.

    A non-empty legacy collection without a contract is rejected.

    A non-empty collection whose persisted vector/chunk contract differs
    from the active configuration is rejected and must be reset/reindexed.
    """

    expected = build_index_contract(
        settings_obj,
        embedding_engine,
        space=space,
    )

    expected_json = _canonical_json(
        expected
    )

    expected_fingerprint = (
        index_contract_fingerprint(
            expected
        )
    )

    metadata = dict(
        collection.metadata or {}
    )

    physical_space = metadata.get(
        "hnsw:space"
    )

    if (
        physical_space is not None
        and physical_space != space
    ):
        raise IndexContractError(
            "Persistent KB index distance-space "
            f"mismatch: stored={physical_space}, "
            f"expected={space}. Reset/reindex the "
            "KB before continuing."
        )

    stored_raw = metadata.get(
        INDEX_CONTRACT_METADATA_KEY
    )

    # ---------------------------------------------------------
    # Legacy collection: no project-level contract persisted.
    # ---------------------------------------------------------
    if stored_raw is None:
        count = int(
            collection.count()
        )

        if count > 0:
            raise IndexContractError(
                "Persistent KB index is non-empty "
                "but has no index contract. "
                "Reset/reindex the KB before using "
                "the current embedding or chunk "
                "configuration."
            )

        _persist_contract(
            collection,
            current_metadata=metadata,
            contract_json=expected_json,
            fingerprint=expected_fingerprint,
        )

        return expected_fingerprint

    # ---------------------------------------------------------
    # Existing project-level contract.
    # ---------------------------------------------------------
    try:
        stored = json.loads(
            str(stored_raw)
        )
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise IndexContractError(
            "Persistent KB index contains an "
            "invalid index contract. "
            "Reset/reindex the KB before "
            "continuing."
        ) from exc

    if stored != expected:
        # If there are no vectors left, there is no stale vector space
        # to protect. The empty collection can adopt the new contract.
        if int(collection.count()) == 0:
            _persist_contract(
                collection,
                current_metadata=metadata,
                contract_json=expected_json,
                fingerprint=(
                    expected_fingerprint
                ),
            )

            return expected_fingerprint

        changed = sorted(
            key
            for key in (
                set(stored)
                | set(expected)
            )
            if stored.get(key)
            != expected.get(key)
        )

        raise IndexContractError(
            "Persistent KB index contract "
            "mismatch for: "
            + ", ".join(changed)
            + ". Reset/reindex the KB before "
            "continuing."
        )

    # ---------------------------------------------------------
    # Contract is semantically identical. Repair only a stale/
    # missing fingerprint, without touching immutable hnsw:* config.
    # ---------------------------------------------------------
    stored_fingerprint = metadata.get(
        INDEX_FINGERPRINT_METADATA_KEY
    )

    if (
        stored_fingerprint
        != expected_fingerprint
    ):
        _persist_contract(
            collection,
            current_metadata=metadata,
            contract_json=expected_json,
            fingerprint=expected_fingerprint,
        )

    return expected_fingerprint
