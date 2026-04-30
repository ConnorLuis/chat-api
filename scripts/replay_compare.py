import argparse
import json
import sys
from json import JSONDecodeError
from pathlib import Path
from typing import List


def replay_compare(compare_group_id: str, log_file_path: str = "../runs/prompt_runs.jsonl"):
    log_path = Path(log_file_path)
    if not log_path.exists():
        print(f"错误 未找到日志文件: {log_path}")
        return 2

    data_list = []
    bad_lines= 0
    total_lines = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            total_lines += 1
            stripped_line = line.strip()
            if not stripped_line:
                continue

            try:
                json_data = json.loads(stripped_line)
                data_list.append(json_data)
            except JSONDecodeError:
                bad_lines += 1
                print(f"日志文件损坏：第 {line_num} 行不是合法 JSON！")

    if bad_lines > 0:
        print(f"\n 解析完成：总行数 {total_lines}，损坏行 {bad_lines}（已自动跳过）")

    records = []
    for record in data_list:
        if (record.get("mode") == "compare" and record.get("compare_group_id") == compare_group_id):
            records.append(record)

    if not records:
        print(f"\n未找到匹配记录！建议检查 /prompt/compare 是否写入 compare_group_id")
        return

    variant_priority = {"A": 0, "B": 1}
    records.sort(key=lambda x: variant_priority.get(x.get("variant"), 99))
    total = len(records)

    print(f"日志地址是：{log_path}")
    print(f"结果匹配数量：{total}")
    if total != 2:
        print(f"警告：记录不完整（期望2条，实际{total}条）")
        print(f"已存在变体：{[r['variant'] for r in records]}")

    for index, record in enumerate(records, 1):
        print(f"   第 {index} 条 | 变体: {record.get('variant')}")
        print(f"   trace_id: {record.get('trace_id')}")
        print(f"   提示词: {record.get('prompt_id')}@{record.get('prompt_version')}")
        print(f"   模型: {record.get('provider')}/{record.get('model')}")
        print(f"   耗时: {record.get('latency_ms')} ms")
        print(f"   输出字符数: {record.get('output_chars')}")
        print(f"   参数: temp={record.get('temperature')}, top_p={record.get('top_p')}, max_tokens={record.get('max_tokens')}")

    if total >= 2:
        a, b = records[0], records[1]
        latency_diff = a["latency_ms"] -b["latency_ms"]
        char_diff = a["output_chars"] - b["output_chars"]
        print("\n对比摘要")
        print(f"耗时差异: A-B={latency_diff}ms | {'A更快' if latency_diff < 0 else 'B更快' if latency_diff > 0 else '耗时相同'}")
        print(f"长度差异: A-B={char_diff}字符 | {'A更长' if char_diff > 0 else 'B更长' if char_diff < 0 else '长度相同'}")

def _find_repo_root(script_path: Path) -> Path:
    """Locate repo root by walking up and finding both 'src' and 'runs' dirs."""
    for p in [script_path.parent, *script_path.parents]:
        try:
            if (p / "src").is_dir() and (p / "runs").is_dir():
                return p
        except Exception:
            continue
    return script_path.parent

def _parse_args(argv: List[str]) -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    repo_root = _find_repo_root(script_path)
    default_log = repo_root / "runs" / "prompt_runs.jsonl"

    parser = argparse.ArgumentParser(
        prog="replay_compare.py",
        description="Replay /prompt/compare results from JSONL run logs by compare_group_id.",
    )
    parser.add_argument(
        "compare_group_id",
        help="compare_group_id returned by /prompt/compare (e.g., 6bea69f7-...).",
    )
    parser.add_argument(
        "--log",
        default=str(default_log),
        help=f"Path to JSONL log file (default: {default_log}).",
    )
    return parser.parse_args(argv)

def main() -> None:
    args = _parse_args(sys.argv[1:])
    code = replay_compare(args.compare_group_id, args.log)
    raise SystemExit(code)


if __name__ == "__main__":
    main()


