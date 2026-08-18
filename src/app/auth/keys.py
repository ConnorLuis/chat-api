from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

from .errors import (
    APIKeyConfigurationError,
)


API_KEY_PREFIX_TAG = "chat_sk"

_API_KEY_PATTERN = re.compile(
    r"^(chat_sk_[0-9a-f]{12})_"
    r"([A-Za-z0-9_-]{40,64})$"
)


@dataclass(
    frozen=True,
    slots=True,
)
class ParsedAPIKey:
    prefix: str
    plaintext: str


@dataclass(
    frozen=True,
    slots=True,
)
class GeneratedAPIKey:
    plaintext: str
    prefix: str
    key_hash: str


def validate_pepper(
    pepper: str,
) -> str:
    normalized = pepper.strip()

    if len(normalized) < 32:
        raise APIKeyConfigurationError(
            "API_KEY_HASH_PEPPER must "
            "contain at least 32 characters"
        )

    return normalized


def hash_api_key(
    plaintext: str,
    *,
    pepper: str,
) -> str:
    normalized_pepper = validate_pepper(
        pepper
    )

    return hmac.new(
        normalized_pepper.encode("utf-8"),
        plaintext.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def parse_api_key(
    value: str,
) -> ParsedAPIKey | None:
    normalized = value.strip()

    match = _API_KEY_PATTERN.fullmatch(
        normalized
    )

    if match is None:
        return None

    return ParsedAPIKey(
        prefix=match.group(1),
        plaintext=normalized,
    )


def generate_api_key(
    *,
    pepper: str,
) -> GeneratedAPIKey:
    public_suffix = secrets.token_hex(6)

    prefix = (
        f"{API_KEY_PREFIX_TAG}_"
        f"{public_suffix}"
    )

    secret = secrets.token_urlsafe(32)

    plaintext = (
        f"{prefix}_{secret}"
    )

    return GeneratedAPIKey(
        plaintext=plaintext,
        prefix=prefix,
        key_hash=hash_api_key(
            plaintext,
            pepper=pepper,
        ),
    )


def verify_api_key(
    plaintext: str,
    *,
    expected_hash: str,
    pepper: str,
) -> bool:
    actual_hash = hash_api_key(
        plaintext,
        pepper=pepper,
    )

    return hmac.compare_digest(
        actual_hash,
        expected_hash,
    )
