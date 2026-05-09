import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.app.core.errors import build_error
from src.app.core.run_store import find_runs_by_trace, find_runs_by_compare_group
from src.app.core.settings import settings
from src.app.llm.schemas import RunsTraceResponse

router = APIRouter()


@router.get("/runs/trace/{trace_id}", response_model=RunsTraceResponse)
def runs_trace(trace_id: str):
    resp = find_runs_by_trace(Path(settings.RUN_LOG_PATH), trace_id=trace_id)
    if len(resp.records) == 0:
        raise HTTPException(status_code=404, detail=f"未能找到{trace_id}对应日志记录")
    return resp

@router.get("/runs/compare/{compare_group_id}")
def runs_compare(compare_group_id: str):
    resp = find_runs_by_compare_group(Path(settings.RUN_LOG_PATH), compare_group_id=compare_group_id)
    if not resp.get("records"):
        raise HTTPException(status_code=404, detail=f"未能找到{compare_group_id}对应日志记录")
    return resp