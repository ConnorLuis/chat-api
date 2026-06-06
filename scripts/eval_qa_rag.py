import argparse
import json
import re
import os
import statistics
from typing import List, Dict
import requests
import math

def load_qa(path: str) -> list[dict]:
    items = []
    required = {"qid","question","expected_keywords","min_hits","expected_sources","expected_titles"}
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception as e:
                raise RuntimeError(f"第{idx}行JSON解析失败：{e}")

            missing = [k for k in required if k not in item]
            if missing:
                raise ValueError(f"第{idx}行缺失字段: {missing}")
            items.append(item)

    return items

def build_chat_payload(item: Dict, provider: str, top_k: int, prompt_id: str, prompt_version: str, temperature: float, max_tokens: int) -> Dict:
    return {
        "provider": provider,
        "messages": [{"role": "user", "content": item["question"]}],
        "use_kb": True,
        "kb_top_k": top_k,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

def call_chat(base_url: str, payload: Dict, timeout: int = 60) -> dict:
    url = base_url.rstrip("/") + "/chat"
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        try:
            data = resp.json()
        except Exception:
            data = None

        error = None
        if resp.status_code != 200:
            if isinstance(data, dict):
                error = json.dumps(data, ensure_ascii=False)[:500]
            else:
                error = resp.text[:500]

        return {
            "http_code": resp.status_code,
            "json": data if isinstance(data, dict) else None,
            "error": error
        }
    except Exception as e:
        return {
            "http_code": -1,
            "json": None,
            "error": str(e)
        }

def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def score_answer(answer: str, expected_keywords: list[str], min_hits: int) -> dict:
    ans_norm = normalize_text(answer)

    uncertainty_patterns = [
        "不确定/需要更多上下文",
        "需要更多上下文",
        "无法基于现有",
        "无法基于提供",
        "无法回答该问题",
        "无法直接回答",
        "文档中未提供",
        "文档中没有提供",
        "资料中未提供",
        "资料中没有提供",
        "未提及相关信息",
        "没有直接涉及",
    ]

    uncertain = any(p in answer for p in uncertainty_patterns)

    hits = []
    for kw in expected_keywords:
        if normalize_text(kw) in ans_norm:
            hits.append(kw)

    return {
        "hits_count": len(hits),
        "hit_keywords": hits,
        "uncertain": uncertain,
        "answer_hit": (not uncertain) and len(hits) >= min_hits
    }

def score_citations(citations: List[Dict], expected_sources: List[str], expected_titles: List[str]) -> Dict:
    has_cit = len(citations) > 0
    src_hit = any(c.get("source") in expected_sources for c in citations)
    tit_hit = any(c.get("title") in expected_titles for c in citations)
    return {
        "has_citations": has_cit,
        "source_hit": src_hit,
        "title_hit": tit_hit,
        "citation_hit": has_cit and src_hit,
        "matched_sources": [c.get("source") for c in citations if c.get("source") in expected_sources],
        "matched_titles":  [c.get("title")  for c in citations if c.get("title")  in expected_titles],
    }

def score_effective_rag(meta: Dict) -> Dict:
    rag = meta.get("rag") or {}
    ctx = meta.get("context_chars", 0)
    enabled = bool(rag.get("enabled", False))
    hits = int(rag.get("hits", 0) or 0)

    return {
        "rag_enabled": enabled,
        "rag_hits": hits,
        "context_chars": ctx,
        "effective_rag": enabled and hits > 0 and ctx > 0,
        "rag_error": rag.get("error") or meta.get("rag_error")
    }

def build_result_record(item: Dict, chat_resp: Dict, args) -> Dict:
    http_code = chat_resp["http_code"]
    error = chat_resp["error"]
    resp_json = chat_resp["json"]

    answer = resp_json.get("answer", "")[:500] if resp_json else ""
    meta = resp_json.get("metadata", {}) if resp_json else {}
    rag = meta.get("rag") or {}
    raw = (rag.get("citations") or [])
    citations = [
        (c.model_dump() if hasattr(c, "model_dump") else c)
        for c in raw
    ]

    ans_score = score_answer(answer, item["expected_keywords"], item["min_hits"])
    cit_score = score_citations(citations, item["expected_sources"], item["expected_titles"])
    rag_score = score_effective_rag(meta)

    return {
        "qid": item["qid"],
        "trace_id": resp_json.get("trace_id") if resp_json else None,
        "question": item["question"],
        "answer": answer,
        "http_code": http_code,
        "latency_ms": meta.get("latency_ms") if resp_json else None,
        "provider": args.provider,
        "model": meta.get("model") if resp_json else None,
        "prompt_id": args.prompt_id,
        "prompt_version": args.prompt_version,
        "rag": rag,
        "context_chars": meta.get("context_chars", 0),
        "citations": citations,
        "answer_score": ans_score,
        "citation_score": cit_score,
        "effective_rag": rag_score["effective_rag"],
        "error": error,
        "note": item.get("note")
    }

def append_jsonl(path: str, obj: Dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def summarize(all_results: List[Dict]) -> Dict:
    total = len(all_results)
    succ = [r for r in all_results if r["http_code"] == 200]
    fail = [r for r in all_results if r["http_code"] != 200]

    ans_hit = sum(1 for r in succ if r["answer_score"]["answer_hit"])
    cit_hit = sum(1 for r in succ if r["citation_score"]["citation_hit"])
    eff_rag = sum(1 for r in succ if r["effective_rag"])
    title_hit = sum(1 for r in succ if r["citation_score"].get("title_hit"))

    lats = [r["latency_ms"] for r in succ if r["latency_ms"] is not None]
    avg_lat = statistics.mean(lats) if lats else 0
    p50 = statistics.median(lats) if lats else 0
    if len(lats) >= 2:
        xs = sorted(lats)
        # 95% 分位的“最小不小于”位置（保守、可解释）
        idx = math.ceil(0.95 * (len(xs) - 1))
        p95 = xs[idx]
    else:
        p95 = None

    return {
        "total": total,
        "success": len(succ),
        "failed": len(fail),
        "answer_hit_rate": round(ans_hit / len(succ), 3) if succ else 0,
        "citation_hit_rate": round(cit_hit / len(succ), 3) if succ else 0,
        "effective_rag_rate": round(eff_rag / len(succ), 3) if succ else 0,
        "title_hit_rate": round(title_hit / len(succ), 3) if succ else 0,
        "avg_latency_ms": round(avg_lat),
        "p50_latency_ms": round(p50),
        "p95_latency_ms": (round(p95) if p95 is not None else None),
        "latency_samples": len(lats),
        "failures": [{"qid": r["qid"], "code": r["http_code"], "error": r["error"]} for r in fail]
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa", default="eval/qa_rag_20.jsonl")
    parser.add_argument("--out", default="eval/results.jsonl")
    parser.add_argument("--summary", default="eval/summary.json")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--prompt-id", default="qa_strict")
    parser.add_argument("--prompt-version", default="v1")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.summary) or ".", exist_ok=True)

    if os.path.exists(args.out):
        open(args.out, "w").close()

    qa_items = load_qa(args.qa)
    if args.limit is not None:
        qa_items = qa_items[:args.limit]

    all_records = []
    for item in qa_items:
        print(f"评测: {item['qid']} | {item['question'][:30]}...")
        payload = build_chat_payload(item, args.provider, args.top_k, args.prompt_id, args.prompt_version, args.temperature, args.max_tokens)
        chat_resp = call_chat(args.base_url, payload)
        record = build_result_record(item, chat_resp, args)
        append_jsonl(args.out, record)
        all_records.append(record)

    summary = summarize(all_records)
    with open(args.summary, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("="*50)
    print(f"总题数: {summary['total']} | 成功: {summary['success']} | 失败: {summary['failed']}")
    print(f"答案命中率: {summary['answer_hit_rate']:.1%}")
    print(f"引用命中率: {summary['citation_hit_rate']:.1%}")
    print(f"有效RAG率: {summary['effective_rag_rate']:.1%}")
    print(f"平均延迟: {summary['avg_latency_ms']}ms")
    print("="*50)

if __name__ == "__main__":
    main()