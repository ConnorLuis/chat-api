import json
from pathlib import Path
from typing import Tuple, List, Dict, Any

from src.app.llm.schemas import RunsTraceResponse

"""
读取jsonl文件，并且返回json格式后的记录，以及坏行数
"""
def _iter_jsonl(path: Path) -> Tuple[List[Dict[str, Any]], int]:
    """读取 JSONL：返回 records + bad_lines（坏行数）。"""
    records: List[Dict[str, Any]] = []
    bad_lines = 0
    if not path.exists():
        return records, bad_lines

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    records.append(obj)
                else:
                    bad_lines += 1
            except:
                bad_lines += 1
    return records, bad_lines

# 根据trace-id在jsonl文件中找寻对应记录
def find_runs_by_trace(path: Path, trace_id: str, mode: str | None = None) -> RunsTraceResponse:
    all_records, bad_lines = _iter_jsonl(path)
    matched: List[Dict[str, Any]] = []
    for r in all_records:
        if r.get("trace_id") != trace_id:
            continue
        if mode is None:
            matched.append(r)
        else:
            if r.get("mode") == mode:
                matched.append(r)
    return RunsTraceResponse(trace_id=trace_id, records=matched, bad_lines=bad_lines)

# 做prompt提示词AB模板比较时会有compare_group_id记录，比较的AB模板返回内容的优劣，方便再次回溯对比
def find_runs_by_compare_group(path: Path, compare_group_id: str) -> Dict[str, Any]:
    all_records,bad_lines = _iter_jsonl(path)

    records: List[Dict[str, Any]] = []
    for r in all_records:
        if r.get("mode") != "compare":
            continue
        if r.get("compare_group_id") != compare_group_id:
            continue
        records.append(r)
    meta = normalize_compare_pair(records)

    resp: Dict[str, Any] = {
        "compare_group_id": compare_group_id,
        "records": meta["records_sorted"],
        "bad_lines": bad_lines,
        "incomplete": meta["incomplete"],
        "present_variants": meta["present_variants"],
        "summary": meta["summary"],
    }
    return resp

# 标准化比较的AB模板
def normalize_compare_pair(records: list[dict]) -> dict:
    priority = {"A": 0, "B": 1}
    records_sorted = sorted(records, key=lambda x: priority.get(x.get("variant"), 99))
    present = [r.get("variant") for r in records_sorted if r.get("variant")]
    present_variants = sorted(set(present), key=lambda v: priority.get(v, 99))

    have_a = any(v == "A" for v in present_variants)
    have_b = any(v == "B" for v in present_variants)
    incomplete = not (have_a and have_b)

    summary: Dict[str, Any] = {}

    if not incomplete:
        a = next(r for r in records_sorted if r.get("variant") == "A")
        b = next(r for r in records_sorted if r.get("variant") == "B")

        latency_a = int(a.get("latency_ms", 0) or  0)
        latency_b = int(b.get("latency_ms", 0) or  0)
        out_a = int(a.get("output_chars", 0) or 0)
        out_b = int(b.get("output_chars", 0) or 0)

        summary = {
            "latency_ms_a": latency_a,
            "latency_ms_b": latency_b,
            "diff_latency_ms": latency_a - latency_b,
            "output_chars_a": out_a,
            "output_chars_b": out_b,
            "output_chars_diff": out_a - out_b,
        }

    return {
        "records_sorted": records_sorted,
        "present_variants": present_variants,
        "incomplete": incomplete,
        "summary": summary,
    }