import time
import uuid
from fastapi import FastAPI, Request

TRACE_ID_HEADER = "x-trace-id"


def get_trace_id(req: Request) -> str:
    return getattr(req.state, "trace_id", "no-trace")


def install_logging_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_trace_and_timing(request: Request, call_next):
        trace_id = request.headers.get(TRACE_ID_HEADER) or str(uuid.uuid4())
        request.state.trace_id = trace_id

        t0 = time.time()
        response = await  call_next(request)
        cost_ms = (time.time() - t0) * 1000

        response.headers[TRACE_ID_HEADER] = trace_id
        print(f"[trace={trace_id}] {request.method} {request.url.path} {response.status_code} {cost_ms:.1f}ms")
        return response