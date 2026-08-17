from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.load_test import (
    LoadTestConfigError,
    default_output_dir,
    load_suite_config,
    run_suite,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a reproducible chat-api HTTP load-test suite and "
            "write raw JSON samples plus a Markdown report."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a load-test suite JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Output directory. Defaults to "
            "benchmarks/results/<suite>-<UTC timestamp>."
        ),
    )
    parser.add_argument(
        "--base-url",
        help="Override base_url from the config file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        suite = load_suite_config(args.config)
        if args.base_url:
            suite = type(suite)(
                suite_name=suite.suite_name,
                base_url=args.base_url.rstrip("/"),
                api_key_env=suite.api_key_env,
                metadata=suite.metadata,
                scenarios=suite.scenarios,
            )
        output_dir = (
            args.output_dir
            if args.output_dir is not None
            else default_output_dir(suite.suite_name)
        )
        suite_result = asyncio.run(
            run_suite(
                suite=suite,
                config_source=str(args.config),
                output_dir=output_dir,
            )
        )
    except (LoadTestConfigError, RuntimeError) as exc:
        print(f"load test failed: {exc}", file=sys.stderr)
        return 2

    print(f"summary: {output_dir / 'summary.json'}")
    print(f"report:  {output_dir / 'report.md'}")
    failed_requests = sum(
        result["summary"]["failed_requests"]
        for result in suite_result["results"]
    )
    if failed_requests:
        print(
            f"load test completed with {failed_requests} failed "
            "measured requests",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
