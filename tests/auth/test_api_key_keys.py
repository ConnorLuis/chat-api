from src.app.auth import (
    generate_api_key,
    hash_api_key,
    parse_api_key,
    verify_api_key,
)


PEPPER = (
    "day9-test-pepper-"
    "0123456789abcdef0123456789abcdef"
)


def test_generate_api_key_shape():
    generated = generate_api_key(
        pepper=PEPPER
    )

    assert generated.plaintext.startswith(
        generated.prefix + "_"
    )
    assert generated.prefix.startswith(
        "chat_sk_"
    )
    assert len(generated.key_hash) == 64

    parsed = parse_api_key(
        generated.plaintext
    )

    assert parsed is not None
    assert parsed.prefix == (
        generated.prefix
    )


def test_hash_is_deterministic_for_same_key():
    generated = generate_api_key(
        pepper=PEPPER
    )

    assert hash_api_key(
        generated.plaintext,
        pepper=PEPPER,
    ) == generated.key_hash


def test_hash_changes_with_pepper():
    generated = generate_api_key(
        pepper=PEPPER
    )

    other = hash_api_key(
        generated.plaintext,
        pepper=(
            "different-day9-pepper-"
            "0123456789abcdef0123456789abcdef"
        ),
    )

    assert other != generated.key_hash


def test_parse_rejects_malformed_keys():
    assert parse_api_key("") is None
    assert parse_api_key("plaintext") is None
    assert parse_api_key(
        "chat_sk_short_secret"
    ) is None


def test_verify_uses_hash_comparison():
    generated = generate_api_key(
        pepper=PEPPER
    )

    assert verify_api_key(
        generated.plaintext,
        expected_hash=(
            generated.key_hash
        ),
        pepper=PEPPER,
    )

    tampered = (
        generated.plaintext[:-1]
        + (
            "A"
            if generated.plaintext[-1]
            != "A"
            else "B"
        )
    )

    assert not verify_api_key(
        tampered,
        expected_hash=(
            generated.key_hash
        ),
        pepper=PEPPER,
    )
