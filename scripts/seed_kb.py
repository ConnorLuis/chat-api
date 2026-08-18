import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_SEED_DIR = "docs/kb_seed"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_MANIFEST = "eval/kb_seed_manifest.jsonl"


def title_from_filename(path: Path) -> str:
    """
    Convert:
      docs/kb_seed/07_KB Ingest & Search.md -> KB Ingest & Search
      docs/kb_seed/08_RAG in Chat or Stream.md -> RAG in Chat/Stream
      docs/kb_seed/02_chat_api_contract.md -> chat api contract
    """
    stem = path.stem
    title = re.sub(r"^\d+_", "", stem)
    title = title.replace("_", " ")
    title = title.replace(" or ", "/")
    return title.strip()


def seed_index(path: Path) -> int | None:
    prefix = path.name.split("_", 1)[0]
    if not prefix.isdigit():
        return None
    return int(prefix)


def iter_seed_paths(seed_dir: Path, start_index: int, end_index: int) -> list[Path]:
    paths: list[Path] = []

    for path in sorted(seed_dir.glob("*.md")):
        idx = seed_index(path)
        if idx is None:
            continue
        if start_index <= idx <= end_index:
            paths.append(path)

    return paths


def build_payload(path: Path) -> dict:
    return {
        "text": path.read_text(encoding="utf-8"),
        "source": path.as_posix(),
        "title": title_from_filename(path),
    }


def reset_runtime_artifacts(kb_dir: Path) -> list[str]:
    removed: list[str] = []

    targets = [
        kb_dir / "chroma",
        kb_dir / "docs",
        kb_dir / "docs.jsonl",
    ]

    for target in targets:
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(target.as_posix())
        elif target.exists():
            target.unlink()
            removed.append(target.as_posix())

    return removed


def post_document(base_url: str, payload: dict, timeout: int) -> dict:
    url = base_url.rstrip("/") + "/kb/documents"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} failed: HTTP {e.code}: {body[:500]}") from e
    except URLError as e:
        raise RuntimeError(
            f"POST {url} failed: {e}. Is uvicorn running at {base_url}?"
        ) from e


def write_manifest(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed KB from docs/kb_seed with stable source/title metadata."
    )

    parser.add_argument("--seed-dir", default=DEFAULT_SEED_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--kb-dir", default="kb")
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--end-index", type=int, default=11)
    parser.add_argument("--timeout", type=int, default=30)

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print selected files and payload metadata without posting to API.",
    )
    parser.add_argument(
        "--reset-runtime",
        action="store_true",
        help="Delete kb/chroma, kb/docs, and kb/docs.jsonl. Run this while uvicorn is stopped.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive reset-runtime operation.",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="POST selected seed docs to /kb/documents. Requires uvicorn running.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    seed_dir = Path(args.seed_dir)
    kb_dir = Path(args.kb_dir)
    manifest_path = Path(args.manifest)

    if not seed_dir.exists():
        print(f"seed dir not found: {seed_dir}", file=sys.stderr)
        return 2

    if args.reset_runtime:
        if not args.yes:
            print(
                "refusing to reset runtime artifacts without --yes",
                file=sys.stderr,
            )
            return 2

        removed = reset_runtime_artifacts(kb_dir)
        print("reset runtime artifacts:")
        if removed:
            for item in removed:
                print(f"  removed: {item}")
        else:
            print("  nothing to remove")

        if not args.ingest:
            print("reset done. Restart uvicorn before running --ingest.")
            return 0

        print(
            "refusing to combine --reset-runtime and --ingest in one run. "
            "Restart uvicorn after reset, then run --ingest.",
            file=sys.stderr,
        )
        return 2

    paths = iter_seed_paths(seed_dir, args.start_index, args.end_index)

    if not paths:
        print(
            f"no seed files selected from {seed_dir} "
            f"for range {args.start_index}-{args.end_index}",
            file=sys.stderr,
        )
        return 2

    records: list[dict] = []

    for path in paths:
        payload = build_payload(path)
        record = {
            "path": path.as_posix(),
            "source": payload["source"],
            "title": payload["title"],
            "text_chars": len(payload["text"]),
        }

        if args.dry_run:
            print(json.dumps(record, ensure_ascii=False))
            records.append(record)
            continue

        if args.ingest:
            response = post_document(args.base_url, payload, args.timeout)
            record.update(
                {
                    "doc_id": response.get("doc_id"),
                    "chunks": response.get("chunks"),
                }
            )
            print(
                f"seeded: {record['path']} | "
                f"title={record['title']} | "
                f"doc_id={record.get('doc_id')} | "
                f"chunks={record.get('chunks')}"
            )
            records.append(record)
            continue

        print(
            "nothing to do. Use --dry-run, --reset-runtime, or --ingest.",
            file=sys.stderr,
        )
        return 2

    write_manifest(manifest_path, records)
    print(f"manifest written: {manifest_path}")
    print(f"selected documents: {len(records)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())