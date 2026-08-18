from __future__ import annotations

from ipaddress import ip_address

from fastapi import Request


UNKNOWN_CLIENT_IP = "unknown"


def normalize_client_host(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip()

    if not normalized:
        return None

    try:
        parsed = ip_address(normalized)

    except ValueError:
        # TestClient and Unix/proxy transports may
        # expose a stable non-IP host identifier.
        return normalized.lower()

    mapped = getattr(
        parsed,
        "ipv4_mapped",
        None,
    )

    if mapped is not None:
        return str(mapped)

    return parsed.compressed


def get_client_ip(
    request: Request,
    *,
    trust_proxy_headers: bool,
) -> str:
    if trust_proxy_headers:
        forwarded = request.headers.get(
            "x-forwarded-for"
        )

        if forwarded:
            first_hop = forwarded.split(
                ",",
                maxsplit=1,
            )[0]

            normalized = normalize_client_host(
                first_hop
            )

            if normalized:
                return normalized

    peer_host = (
        request.client.host
        if request.client is not None
        else None
    )

    return (
        normalize_client_host(peer_host)
        or UNKNOWN_CLIENT_IP
    )
