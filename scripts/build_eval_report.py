import argparse
import json
import os
import sys
import textwrap
from typing import List, Dict

def load_summary(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_results(path: str) -> list[dict]:
    results = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except Exception as e:
                raise RuntimeError(f"第{idx}行 results JSON 解析失败: {e}")
    return results

def check_gated(summary: Dict, thresholds: Dict) -> Dict:
    """
    校验回归门槛
    thresholds 包含: min_answer_hit, min_citation_hit, min_effective_rag, max_p95_latency_ms
    """
    p95 = summary.get("p95_latency_ms")
    p95_passed = (p95 is None) or (p95 <= thresholds["max_p95_latency_ms"])
    return {
        "title_hit_rate": {
            "value": round(summary.get("title_hit_rate", 0), 3),
            "threshold": thresholds["min_title_hit"],
            "passed": summary.get("title_hit_rate", 0) >= thresholds["min_title_hit"]
        },
        "answer_hit_rate": {
            "value": round(summary["answer_hit_rate"], 3),
            "threshold": thresholds["min_answer_hit"],
            "passed": summary["answer_hit_rate"] >= thresholds["min_answer_hit"]
        },
        "citation_hit_rate": {
            "value": round(summary["citation_hit_rate"], 3),
            "threshold": thresholds["min_citation_hit"],
            "passed": summary["citation_hit_rate"] >= thresholds["min_citation_hit"]
        },
        "effective_rag_rate": {
            "value": round(summary["effective_rag_rate"], 3),
            "threshold": thresholds["min_effective_rag"],
            "passed": summary["effective_rag_rate"] >= thresholds["min_effective_rag"]
        },
        "p95_latency_ms": {
            "value": p95,
            "threshold": thresholds["max_p95_latency_ms"],
            "passed": p95_passed
        },
        "failed_count": {
            "value": summary.get("failed", 0),
            "threshold": 0,
            "passed": summary.get("failed", 0) == 0
        },
    }

def collect_failures(results: List[Dict]) -> List[Dict]:
    """收集失败/弱案例：answer_hit / citation_hit / effective_rag 失败，或 title_hit 弱"""
    failures = []
    for res in results:
        if res.get("http_code") != 200:
            continue

        ans_hit = res["answer_score"]["answer_hit"]
        cit_hit = res["citation_score"]["citation_hit"]
        eff_rag = res["effective_rag"]
        title_hit = res["citation_score"]["title_hit"]

        if not ans_hit or not cit_hit or not eff_rag or not title_hit:
            failures.append({
                "qid": res["qid"],
                "question": res["question"],
                "answer_hit": ans_hit,
                "citation_hit": cit_hit,
                "title_hit": title_hit,
                "effective_rag": eff_rag,
                "error": res.get("error")
            })
    return failures

def render_report(summary: Dict, results: List[Dict], gates: Dict) -> str:
    """渲染 Markdown 报告（严格遵循指定格式）"""
    # 补充计算 title_hit_rate
    success_results = [r for r in results if r.get("http_code") == 200]
    title_hit_count = sum(1 for r in success_results if r["citation_score"]["title_hit"])
    title_hit_rate = round(title_hit_count / len(success_results), 3) if success_results else 0.0

    # 1. Summary 表格
    summary_md = textwrap.dedent(f"""
    # RAG Evaluation Report

    ## 1. Summary

    | Metric | Value |
    |---|---:|
    | total | {summary['total']} |
    | success | {summary['success']} |
    | failed | {summary['failed']} |
    | answer_hit_rate | {summary['answer_hit_rate'] * 100:.1f}% |
    | citation_hit_rate | {summary['citation_hit_rate'] * 100:.1f}% |
    | effective_rag_rate | {summary['effective_rag_rate'] * 100:.1f}% |
    | title_hit_rate | {title_hit_rate * 100:.1f}% |
    | avg_latency_ms | {summary['avg_latency_ms']} |
    | p95_latency_ms | {summary['p95_latency_ms']} |

    """)

    # 2. Regression Gates 表格
    gates_md = "## 2. Regression Gates\n\n| Gate | Value | Threshold | Status |\n|---|---:|---:|---|\n"
    for gate, data in gates.items():
        status = "PASS" if data["passed"] else "FAIL"
        if gate == "p95_latency_ms":
            val = data["value"] if data["value"] is not None else "N/A"
            thd = f"<= {data['threshold']}"
        elif gate == "failed_count":
            val = data["value"]
            thd = f"== {data['threshold']}"
        else:
            val = f"{data['value'] * 100:.1f}%"
            thd = f">= {data['threshold'] * 100:.1f}%"
        gates_md += f"| {gate} | {val} | {thd} | {status} |\n"

    # 3. Per-question Results 表格
    question_md = "\n## 3. Per-question Results\n\n"
    question_md += "| qid | answer_hit | citation_hit | title_hit | effective_rag | latency_ms | citations |\n"
    question_md += "|---|---|---|---|---|---:|---|\n"
    for res in success_results:
        qid = res["qid"]
        ans = mark(res["answer_score"]["answer_hit"])
        cit = mark(res["citation_score"]["citation_hit"])
        title = mark(res["citation_score"]["title_hit"])
        eff = mark(res["effective_rag"])
        lat = res["latency_ms"] or "-"
        citation_titles = []
        for c in res.get("citations", []):
            t = c.get("title")
            if t and t not in citation_titles:
                citation_titles.append(t)

        citations_str = ", ".join(citation_titles) if citation_titles else "-"
        question_md += f"| {qid} | {ans} | {cit} | {title} | {eff} | {lat} | {citations_str} |\n"

    # 4. Failed / Weak Cases
    failures = collect_failures(results)
    fail_md = "\n## 4. Failed / Weak Cases\n\n"
    if not failures:
        fail_md += "All cases passed!\n"
    else:
        for fail in failures:
            fail_md += (
                f"### {fail['qid']}: {fail['question']}\n"
                f"- answer_hit: {mark(fail['answer_hit'])}\n"
                f"- citation_hit: {mark(fail['citation_hit'])}\n"
                f"- title_hit: {mark(fail['title_hit'])}\n"
                f"- effective_rag: {mark(fail['effective_rag'])}\n\n"
            )

    # 5. Engineering Notes
    note_md = textwrap.dedent("""
    ## 5. Engineering Notes

    - Day19 fixed QA seed pollution.
    - Added extract_index_text.
    - Added candidate_k=50.
    - Added query-aware rerank.
    - Added uncertain-answer guard.
    """)

    return summary_md + gates_md + question_md + fail_md + note_md

def mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"

def main():
    parser = argparse.ArgumentParser(description="Build RAG Evaluation Report (Interview Material)")
    parser.add_argument("--results", required=True, help="Path to results.jsonl")
    parser.add_argument("--summary", required=True, help="Path to summary.json")
    parser.add_argument("--out", required=True, help="Output report.md path")
    # 门槛阈值
    parser.add_argument("--min-answer-hit", type=float, default=0.90, help="Min answer hit rate")
    parser.add_argument("--min-citation-hit", type=float, default=0.95, help="Min citation hit rate")
    parser.add_argument("--min-effective-rag", type=float, default=0.95, help="Min effective RAG rate")
    parser.add_argument("--min-title-hit", type=float, default=0.85, help="Min title hit rate")
    parser.add_argument("--max-p95-latency-ms", type=int, default=6000, help="Max p95 latency (ms)")
    # 严格模式
    parser.add_argument("--strict", action="store_true", help="Exit 1 if any gate failed")

    args = parser.parse_args()

    # 创建输出目录
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    # 加载数据
    summary = load_summary(args.summary)
    results = load_results(args.results)

    # 校验回归门槛
    thresholds = {
        "min_answer_hit": args.min_answer_hit,
        "min_citation_hit": args.min_citation_hit,
        "min_effective_rag": args.min_effective_rag,
        "max_p95_latency_ms": args.max_p95_latency_ms,
        "min_title_hit": args.min_title_hit,
    }
    gates = check_gated(summary, thresholds)

    # 渲染并写入报告
    report = render_report(summary, results, gates)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report.strip())

    print(f"Report generated: {args.out}")

    # 严格模式：任意门槛不通过则退出失败
    if args.strict:
        all_passed = all(data["passed"] for data in gates.values())
        if not all_passed:
            print("Regression gates failed!")
            sys.exit(1)
        else:
            print("All regression gates passed!")


if __name__ == "__main__":
    main()