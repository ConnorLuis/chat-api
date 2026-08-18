import json
from pathlib import Path

from scripts.run_rag_eval_workflow import print_summary


def test_print_summary_outputs_core_metrics(tmp_path, capsys):
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "total": 20,
                "success": 20,
                "failed": 0,
                "answer_hit_rate": 0.9,
                "citation_hit_rate": 1.0,
                "effective_rag_rate": 1.0,
                "title_hit_rate": 0.95,
                "avg_latency_ms": 1958,
                "p50_latency_ms": 1706,
                "p95_latency_ms": 5921,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print_summary(summary)

    out = capsys.readouterr().out

    assert "RAG eval summary" in out
    assert "answer_hit_rate: 0.9" in out
    assert "citation_hit_rate: 1.0" in out
    assert "p95_latency_ms: 5921" in out


def test_print_summary_handles_missing_file(tmp_path, capsys):
    print_summary(tmp_path / "missing.json")

    err = capsys.readouterr().err
    assert "summary not found" in err