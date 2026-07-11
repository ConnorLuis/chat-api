from fastapi import (
    Depends,
    FastAPI,
)
from fastapi.testclient import (
    TestClient,
)

from src.app.auth.dependency import (
    require_api_key,
)
from src.app.auth.http import (
    install_api_key_exception_handlers,
)
from src.app.services.api_key_service import (
    APIKeyService,
)


def test_auth_disabled_allows_whoami(
    auth_context,
    monkeypatch,
):
    monkeypatch.setenv(
        "API_AUTH_ENABLED",
        "false",
    )

    response = auth_context[
        "client"
    ].get("/auth/whoami")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": False,
        "auth_enabled": False,
        "key_id": None,
        "key_prefix": None,
        "key_name": None,
        "authentication_method": None,
        "authenticated_at": None,
    }


def test_missing_key_has_stable_error(
    auth_context,
):
    response = auth_context[
        "client"
    ].get("/auth/whoami")

    assert response.status_code == 401
    assert response.headers[
        "www-authenticate"
    ] == "Bearer"

    assert response.json() == {
        "detail": {
            "code": "api_key_missing",
            "message": (
                "API key is required"
            ),
        }
    }


def test_x_api_key_authenticates(
    auth_context,
):
    response = auth_context[
        "client"
    ].get(
        "/auth/whoami",
        headers={
            "X-API-Key": (
                auth_context["api_key"]
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["authenticated"] is True
    assert body["key_id"] == (
        auth_context["key_id"]
    )
    assert body["key_prefix"] == (
        auth_context["prefix"]
    )
    assert body["key_name"] == (
        auth_context["name"]
    )
    assert (
        body["authentication_method"]
        == "x-api-key"
    )

    serialized = str(body)

    assert (
        auth_context["api_key"]
        not in serialized
    )
    assert "key_hash" not in body


def test_bearer_authenticates(
    auth_context,
):
    response = auth_context[
        "client"
    ].get(
        "/auth/whoami",
        headers={
            "Authorization": (
                "Bearer "
                + auth_context["api_key"]
            )
        },
    )

    assert response.status_code == 200
    assert (
        response.json()[
            "authentication_method"
        ]
        == "bearer"
    )


def test_matching_headers_are_allowed(
    auth_context,
):
    api_key = auth_context["api_key"]

    response = auth_context[
        "client"
    ].get(
        "/auth/whoami",
        headers={
            "Authorization": (
                f"Bearer {api_key}"
            ),
            "X-API-Key": api_key,
        },
    )

    assert response.status_code == 200
    assert (
        response.json()[
            "authentication_method"
        ]
        == "bearer"
    )


def test_conflicting_headers_are_invalid(
    auth_context,
):
    response = auth_context[
        "client"
    ].get(
        "/auth/whoami",
        headers={
            "Authorization": (
                "Bearer "
                + auth_context["api_key"]
            ),
            "X-API-Key": (
                "chat_sk_ffffffffffff_"
                + "A" * 43
            ),
        },
    )

    assert response.status_code == 401
    assert response.json()[
        "detail"
    ]["code"] == "api_key_invalid"


def test_malformed_authorization_is_invalid(
    auth_context,
):
    response = auth_context[
        "client"
    ].get(
        "/auth/whoami",
        headers={
            "Authorization": "Basic abc",
        },
    )

    assert response.status_code == 401
    assert response.json()[
        "detail"
    ]["code"] == "api_key_invalid"


def test_unknown_key_is_invalid(
    auth_context,
):
    unknown = (
        "chat_sk_ffffffffffff_"
        + "A" * 43
    )

    response = auth_context[
        "client"
    ].get(
        "/auth/whoami",
        headers={
            "X-API-Key": unknown,
        },
    )

    assert response.status_code == 401
    assert response.json()[
        "detail"
    ]["code"] == "api_key_invalid"


def test_revoked_key_has_stable_error(
    auth_context,
):
    with auth_context[
        "session_factory"
    ]() as session:
        APIKeyService(
            session
        ).revoke_key(
            auth_context["key_id"]
        )

    response = auth_context[
        "client"
    ].get(
        "/auth/whoami",
        headers={
            "X-API-Key": (
                auth_context["api_key"]
            )
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "code": "api_key_revoked",
            "message": (
                "API key has been revoked"
            ),
        }
    }


def test_openai_path_uses_openai_error_shape(
    auth_context,
):
    mini_app = FastAPI()

    install_api_key_exception_handlers(
        mini_app
    )

    @mini_app.get(
        "/v1/protected",
        dependencies=[
            Depends(require_api_key),
        ],
    )
    def protected():
        return {"ok": True}

    response = TestClient(
        mini_app
    ).get("/v1/protected")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "message": (
                "API key is required"
            ),
            "type": (
                "authentication_error"
            ),
            "param": None,
            "code": "api_key_missing",
        }
    }


def test_public_paths_do_not_require_api_key(
    auth_context,
):
    client = auth_context["client"]

    for path in (
        "/health",
        "/ready",
        "/openapi.json",
        "/docs",
        "/redoc",
        "/demo",
    ):
        response = client.get(path)

        assert response.status_code == 200, (
            path,
            response.text,
        )


def test_native_business_routes_require_api_key(
    auth_context,
):
    client = auth_context["client"]

    requests = [
        (
            "post",
            "/chat",
            {
                "provider": "mock",
                "messages": [
                    {
                        "role": "user",
                        "content": "protected",
                    }
                ],
            },
        ),
        (
            "get",
            "/conversations",
            None,
        ),
        (
            "get",
            "/usage/pricing",
            None,
        ),
        (
            "get",
            "/prompts",
            None,
        ),
        (
            "get",
            (
                "/kb/search"
                "?q=protected&top_k=1"
            ),
            None,
        ),
        (
            "get",
            "/runs/trace/not-found",
            None,
        ),
    ]

    for method, path, payload in requests:
        if method == "post":
            response = client.post(
                path,
                json=payload,
            )
        else:
            response = client.get(path)

        assert response.status_code == 401, (
            path,
            response.text,
        )

        assert response.json() == {
            "detail": {
                "code": "api_key_missing",
                "message": (
                    "API key is required"
                ),
            }
        }


def test_openai_business_route_requires_bearer_compatible_key(
    auth_context,
):
    response = auth_context[
        "client"
    ].post(
        "/v1/chat/completions",
        json={
            "model": "mock-model",
            "messages": [
                {
                    "role": "user",
                    "content": "protected",
                }
            ],
        },
    )

    assert response.status_code == 401
    assert response.headers[
        "www-authenticate"
    ] == "Bearer"

    assert response.json() == {
        "error": {
            "message": (
                "API key is required"
            ),
            "type": (
                "authentication_error"
            ),
            "param": None,
            "code": "api_key_missing",
        }
    }


def test_x_api_key_allows_native_chat(
    auth_context,
):
    response = auth_context[
        "client"
    ].post(
        "/chat",
        headers={
            "X-API-Key": (
                auth_context["api_key"]
            )
        },
        json={
            "provider": "mock",
            "model": "day9-native-model",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "day9 native "
                        "authentication"
                    ),
                }
            ],
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["metadata"][
        "provider"
    ] == "mock"
    assert body["metadata"][
        "model"
    ] == "day9-native-model"


def test_bearer_allows_openai_compatible_chat(
    auth_context,
):
    response = auth_context[
        "client"
    ].post(
        "/v1/chat/completions",
        headers={
            "Authorization": (
                "Bearer "
                + auth_context["api_key"]
            )
        },
        json={
            "provider": "mock",
            "model": "day9-openai-model",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "day9 bearer "
                        "authentication"
                    ),
                }
            ],
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["object"] == (
        "chat.completion"
    )
    assert body["model"] == (
        "day9-openai-model"
    )
