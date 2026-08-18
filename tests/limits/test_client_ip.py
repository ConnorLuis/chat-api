from fastapi import Request

from src.app.limits import (
    get_client_ip,
    normalize_client_host,
)


def build_request(
    *,
    peer_host: str,
    forwarded_for: str | None = None,
) -> Request:
    headers = []

    if forwarded_for is not None:
        headers.append((
            b"x-forwarded-for",
            forwarded_for.encode("ascii"),
        ))

    return Request({
        "type": "http",
        "method": "GET",
        "path": "/chat",
        "headers": headers,
        "client": (
            peer_host,
            12345,
        ),
        "server": (
            "testserver",
            80,
        ),
        "scheme": "http",
        "query_string": b"",
    })


def test_proxy_header_is_ignored_by_default():
    request = build_request(
        peer_host="203.0.113.10",
        forwarded_for="198.51.100.20",
    )

    assert get_client_ip(
        request,
        trust_proxy_headers=False,
    ) == "203.0.113.10"


def test_trusted_proxy_uses_first_hop():
    request = build_request(
        peer_host="203.0.113.10",
        forwarded_for=(
            "198.51.100.20, 10.0.0.1"
        ),
    )

    assert get_client_ip(
        request,
        trust_proxy_headers=True,
    ) == "198.51.100.20"


def test_empty_forwarded_value_falls_back():
    request = build_request(
        peer_host="203.0.113.10",
        forwarded_for=" ",
    )

    assert get_client_ip(
        request,
        trust_proxy_headers=True,
    ) == "203.0.113.10"


def test_ipv4_mapped_ipv6_is_normalized():
    assert normalize_client_host(
        "::ffff:192.0.2.10"
    ) == "192.0.2.10"
