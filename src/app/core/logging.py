import logging
import time
import uuid

from fastapi import FastAPI, Request

from src.app.core.settings import settings


# HTTP 请求/响应中用于传递 trace ID 的 header。
TRACE_ID_HEADER = "x-trace-id"

# 业务专属 logger。
logger = logging.getLogger("llm_chat_log")


def get_trace_id(req: Request) -> str:
    """Return the request trace ID installed by the middleware."""

    return getattr(req.state, "trace_id", "no-trace")


def install_logging_middleware(app: FastAPI) -> None:
    """Install request trace propagation and latency logging."""

    @app.middleware("http")
    async def add_trace_and_timing(
        request: Request,
        call_next,
    ):
        trace_id = (
            request.headers.get(TRACE_ID_HEADER)
            or str(uuid.uuid4())
        )
        request.state.trace_id = trace_id

        started_at = time.perf_counter()
        response = await call_next(request)
        latency_ms = (
            time.perf_counter() - started_at
        ) * 1000

        response.headers[TRACE_ID_HEADER] = trace_id
        logger.info(
            "[trace=%s] %s %s %s %.1fms",
            trace_id,
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
        )
        return response


def setup_logging() -> None:
    """Configure application logs without changing uvicorn semantics."""

    level = getattr(
        logging,
        settings.APP_LOG_LEVEL,
    )
    # The application logger is independent of uvicorn's log level. This
    # explicit level makes benchmark logging conditions reproducible.
    logger.setLevel(level)
    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s - %(name)s - "
            "%(levelname)s - %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler()],
    )
