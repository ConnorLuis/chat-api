from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.responses import Response

from .errors import openai_error_response


def _validation_param(
    error: dict[str, Any],
) -> str | None:
    location = error.get("loc") or ()

    parts = [
        str(part)
        for part in location
        if part not in {
            "body",
            "__root__",
        }
    ]

    return ".".join(parts) or None


class OpenAICompatRoute(APIRoute):
    """只转换 OpenAI-compatible 路由的请求校验错误。"""

    def get_route_handler(
        self,
    ) -> Callable[
        [Request],
        Coroutine[Any, Any, Response],
    ]:
        original_handler = super().get_route_handler()

        async def custom_handler(
            request: Request,
        ) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                errors = exc.errors()
                first_error = errors[0] if errors else {}

                param = _validation_param(first_error)
                message = first_error.get(
                    "msg",
                    "Invalid request.",
                )

                if param:
                    message = (
                        f"Invalid value for '{param}': "
                        f"{message}"
                    )

                return openai_error_response(
                    status_code=400,
                    message=message,
                    error_type="invalid_request_error",
                    param=param,
                    code="invalid_request",
                )

        return custom_handler
