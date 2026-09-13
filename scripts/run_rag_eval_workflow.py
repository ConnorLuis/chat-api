import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_QA = "eval/qa_rag_20.jsonl"
DEFAULT_RESULTS = "eval/results/rag_eval_20_workflow.jsonl"
DEFAULT_SUMMARY = "eval/results/rag_eval_20_workflow_summary.json"
DEFAULT_REPORT = "eval/reports/rag_eval_report_workflow.md"
DEFAULT_MANIFEST = "eval/kb_seed_manifest.jsonl"


def run_cmd(cmd: list[str]) -> None:
    print()
    print("$ " + " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def check_server(base_url: str, timeout: int) -> None:
    url = base_url.rstrip("/") + "/health"
    try:
        with urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            if resp.status != 200:
                raise RuntimeError(f"GET {url} returned HTTP {resp.status}: {body[:300]}")
    except URLError as e:
        raise SystemExit(
            f"server is not reachable at {base_url}. "
            f"Start uvicorn first, then rerun this workflow. Detail: {e}"
        ) from e

def get_kb_document_total(base_url: str, timeout: int) -> int:
    url = (
        base_url.rstrip("/")
        + "/kb/documents?limit=1&offset=0&include_deleted=false"
    )
    try:
        with urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            if resp.status != 200:
                raise RuntimeError(
                    f"GET {url} returned HTTP {resp.status}: {body[:300]}"
                )
            payload = json.loads(body)
    except URLError as e:
        raise SystemExit(f"failed to inspect KB state at {url}: {e}") from e

    return int(payload.get("total", 0))


def require_clean_kb(base_url: str, timeout: int) -> None:
    total = get_kb_document_total(base_url, timeout)
    if total != 0:
        raise SystemExit(
            "reproducible RAG eval requires an empty active KB before seeding; "
            f"found {total} active documents. Run --reset-runtime, restart "
            "uvicorn, then rerun; or use --skip-seed to evaluate the current "
            "live KB intentionally."
        )


def read_manifest_records(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"seed manifest not found after ingest: {path}")
    records = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            records.append(json.loads(raw))
    return records


def verify_seeded_kb_state(
    base_url: str,
    manifest_path: Path,
    timeout: int,
) -> None:
    records = read_manifest_records(manifest_path)
    if not records:
        raise SystemExit("seed manifest is empty after ingest")

    missing_hash = [
        item.get("path", "<unknown>")
        for item in records
        if not item.get("content_sha256")
    ]
    if missing_hash:
        raise SystemExit(
            "seed manifest is missing content_sha256 for: "
            + ", ".join(missing_hash)
        )

    total = get_kb_document_total(base_url, timeout)
    if total != len(records):
        raise SystemExit(
            "seeded KB state does not match manifest: "
            f"active_documents={total}, manifest_records={len(records)}"
        )


def warmup_provider(base_url: str, provider: str, timeout: int) -> None:
    url = base_url.rstrip("/") + "/chat"
    payload = {
        "provider": provider,
        "messages": [{"role": "user", "content": "ping"}],
        "use_kb": False,
        "max_tokens": 16,
        "temperature": 0.0,
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print()
    print(f"Warm up provider: {provider}")

    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status != 200:
                raise RuntimeError(
                    f"POST {url} returned HTTP {resp.status}: {body[:300]}"
                )
    except URLError as e:
        raise SystemExit(
            f"provider warmup failed at {base_url}. "
            f"Check provider={provider} and OLLAMA_BASE_URL. Detail: {e}"
        ) from e

    print("Warmup done.")


def print_summary(summary_path: Path) -> None:
    if not summary_path.exists():
        print(f"summary not found: {summary_path}", file=sys.stderr)
        return

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    print()
    print("=" * 60)
    print("RAG eval summary")
    print("=" * 60)
    for key in [
        "total",
        "success",
        "failed",
        "answer_hit_rate",
        "citation_hit_rate",
        "effective_rag_rate",
        "title_hit_rate",
        "avg_latency_ms",
        "p50_latency_ms",
        "p95_latency_ms",
    ]:
        print(f"{key}: {data.get(key)}")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run reproducible KB seed + QA20 RAG eval + strict report workflow."
    )

    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--qa", default=DEFAULT_QA)
    parser.add_argument("--results", default=DEFAULT_RESULTS)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--prompt-id", default="qa_strict")
    parser.add_argument("--prompt-version", default="v1")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument(
        "--skip-warmup",
        action="store_true",
        help="Skip provider warmup before eval.",
    )

    parser.add_argument(
        "--reset-runtime",
        action="store_true",
        help="Reset kb runtime artifacts before seeding. Uvicorn should be stopped for the reset step.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive reset-runtime operation.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip KB seeding and only run eval/report against current live KB.",
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Skip build_eval_report.py.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="Run build_eval_report.py with --strict. Enabled by default.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.reset_runtime:
        if not args.yes:
            raise SystemExit("refusing to reset runtime artifacts without --yes")

        run_cmd([
            sys.executable,
            "scripts/seed_kb.py",
            "--reset-runtime",
            "--yes",
        ])
        print()
        print(
            "Runtime artifacts were reset. Restart uvicorn, then rerun this workflow "
            "without --reset-runtime to seed/evaluate."
        )
        return 0

    check_server(args.base_url, timeout=10)

    if not args.skip_seed:
        require_clean_kb(args.base_url, timeout=args.timeout)
        run_cmd([
            sys.executable,
            "scripts/seed_kb.py",
            "--ingest",
            "--base-url",
            args.base_url,
            "--manifest",
            args.manifest,
            "--timeout",
            str(args.timeout),
        ])
        verify_seeded_kb_state(
            args.base_url,
            Path(args.manifest),
            timeout=args.timeout,
        )

    if not args.skip_warmup:
        warmup_provider(args.base_url, args.provider, timeout=args.timeout)

    run_cmd([
        sys.executable,
        "scripts/eval_qa_rag.py",
        "--qa",
        args.qa,
        "--out",
        args.results,
        "--summary",
        args.summary,
        "--base-url",
        args.base_url,
        "--provider",
        args.provider,
        "--top-k",
        str(args.top_k),
        "--prompt-id",
        args.prompt_id,
        "--prompt-version",
        args.prompt_version,
        "--temperature",
        str(args.temperature),
        "--max-tokens",
        str(args.max_tokens),
    ])

    if not args.skip_report:
        cmd = [
            sys.executable,
            "scripts/build_eval_report.py",
            "--results",
            args.results,
            "--summary",
            args.summary,
            "--out",
            args.report,
        ]
        if args.strict:
            cmd.append("--strict")
        run_cmd(cmd)

    print_summary(Path(args.summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())