from __future__ import annotations

from fastapi.responses import JSONResponse

from .schemas import (
    OpenAIErrorDetail,
    OpenAIErrorResponse,
    OpenAIGatewayMetadata,
)


def openai_error_response(
    *,
    status_code: int,
    message: str,
    error_type: str,
    param: str | None = None,
    code: str | None = None,
    provider_execution: dict | None = None,
) -> JSONResponse:
    payload = OpenAIErrorResponse(
        error=OpenAIErrorDetail(
            message=message,
            type=error_type,
            param=param,
            code=code,
        ),
        gateway=(
            OpenAIGatewayMetadata(
                provider_execution=(
                    provider_execution
                )
            )
            if provider_execution is not None
            else None
        ),
    )

    content = payload.model_dump()

    if payload.gateway is None:
        content.pop("gateway", None)

    return JSONResponse(
        status_code=status_code,
        content=content,
    )
