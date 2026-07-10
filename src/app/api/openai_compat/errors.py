from __future__ import annotations

from fastapi.responses import JSONResponse

from .schemas import OpenAIErrorDetail, OpenAIErrorResponse


def openai_error_response(
    *,
    status_code: int,
    message: str,
    error_type: str,
    param: str | None = None,
    code: str | None = None,
) -> JSONResponse:
    payload = OpenAIErrorResponse(
        error=OpenAIErrorDetail(
            message=message,
            type=error_type,
            param=param,
            code=code,
        )
    )

    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
    )
