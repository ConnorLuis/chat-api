# Day22 Demo Storyline

## Goal

Day22 的目标是把 chat-api 已完成的能力串成一条可演示故事线：

PromptHub → RAG → Streaming SSE → A/B Compare → Replay → Error Demo → Eval Report

这不是新增底层能力，而是把已有能力组织成一个面试/展示可讲清楚的完整闭环。

---

## 1. Service Health

Command:

```bash
curl -s http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

Talk track:

* FastAPI 服务已启动。
* 后续演示围绕 `/chat`、`/chat/stream`、PromptHub、RAG、Replay 和 Eval Report 展开。

---

## 2. PromptHub

Command:

```bash
curl -s http://localhost:8000/prompts | python -m json.tool
```

Expected:

* 能看到 `chat`、`qa_strict` 等 prompt_id。
* 每个 prompt_id 下有 version。

Talk track:

* Prompt 不硬编码在业务代码里。
* 通过 `prompt_id` / `prompt_version` 选择 prompt。
* A/B Compare 和 Run Replay 都会记录 prompt 元数据。

---

## 3. RAG Sync Chat

Question:

```text
docs.jsonl 的作用是什么？
```

Command:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"docs.jsonl 的作用是什么？"}],
    "use_kb":true,
    "kb_top_k":3,
    "prompt_id":"qa_strict",
    "prompt_version":"v1",
    "temperature":0.1,
    "top_p":0.9,
    "max_tokens":256
  }' | python -m json.tool
```

Expected:

* `metadata.rag.enabled=true`
* `metadata.rag.hits > 0`
* `metadata.rag.candidate_k=50`
* `metadata.rag.citations` 非空
* answer 基于 KB 回答，而不是泛化回答。

Talk track:

* RAG 链路：query → Chroma candidate_k → query-aware rerank → top_k context → LLM answer。
* citations 支持 `doc_id/chunk_id/source/title` 溯源。
* `candidate_k` 用于先召回更大候选池，`top_k` 控制最终注入上下文数量。

---

## 4. RAG Streaming SSE

Question:

```text
candidate_k 在 RAG 中用来做什么？
```

Command:

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"candidate_k 在 RAG 中用来做什么？"}],
    "use_kb":true,
    "kb_top_k":3,
    "prompt_id":"qa_strict",
    "prompt_version":"v1",
    "max_tokens":128
  }'
```

Expected SSE order:

```text
event: meta
event: token
event: usage
event: done
```

Expected:

* `meta.data.rag` 有 `enabled/top_k/hits/context_chars/candidate_k`。
* `usage.data.rag.citations` 包含引用。
* token 持续流式输出。

Talk track:

* 同步接口和流式接口都支持 RAG。
* Stream 接口用 SSE 承载 token 增量。
* citations 放在 usage 阶段，避免 meta 过重。

---

## 5. Prompt A/B Compare

Command:

```bash
curl -s -X POST http://localhost:8000/prompt/compare \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"一句话解释 RAG 的作用"}],
    "max_tokens":128,
    "temperature":0.3,
    "top_p":0.9,
    "prompt_a":{"prompt_id":"chat","prompt_version":"v1","prompt_vars":{}},
    "prompt_b":{"prompt_id":"qa_strict","prompt_version":"v1","prompt_vars":{}}
  }' | python -m json.tool
```

Expected:

* `compare_group_id`
* `a.trace_id`
* `b.trace_id`
* `metrics.latency_ms_*`
* `metrics.output_chars_*`

Talk track:

* 同一输入可对比不同 prompt。
* A/B 结果写入 run log。
* `compare_group_id` 支持后续回放。

---

## 6. Replay

Trace replay:

```bash
curl -s http://localhost:8000/runs/trace/<trace_id> | python -m json.tool
```

Compare replay:

```bash
curl -s http://localhost:8000/runs/compare/<compare_group_id> | python -m json.tool
```

Expected:

* trace 查询返回 records。
* compare 查询返回 A/B records 和 summary。
* 找不到 trace_id 时返回 404。

Talk track:

* trace_id 是线上排障入口。
* run log 支持 prompt、latency、rag、citations 等证据回放。
* compare_group_id 可以聚合一次 A/B 实验的两个变体。

---

## 7. Error Demo

Sync error contract:

```text
/chat 下游失败 → HTTP 502 + structured detail
```

Stream error contract:

```text
/chat/stream 下游失败 → HTTP 200 + event:error
```

Optional setup:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:1
```

Then restart service and test `/chat` / `/chat/stream`.

Talk track:

* 同步接口用 HTTP 状态表达下游失败。
* 流式接口由于 SSE 通道已建立，业务失败通过 `event:error` 表达。
* 两者都带 `trace_id/provider/model/latency/error`。

---

## 8. RAG Eval Report

Generate report:

```bash
python scripts/build_eval_report.py \
  --results eval/results/rag_eval_20.jsonl \
  --summary eval/results/rag_eval_20_summary.json \
  --out eval/reports/rag_eval_report.md \
  --strict
```

Show report:

```bash
head -n 80 eval/reports/rag_eval_report.md
```

Expected:

* `answer_hit_rate = 95.0%`
* `citation_hit_rate = 100.0%`
* `effective_rag_rate = 100.0%`
* `failed_count = 0`
* strict gate PASS

Talk track:

* RAG 不只功能可用，还有离线 QA20 评测。
* strict gate 防止后续改动导致 RAG 退化。
* title_hit 是诊断项，citation_hit/effective_rag 是主链路指标。

---

## Demo Talk Track

一句话总览：

这个项目从 LLM 服务出发，逐步加入 PromptHub、RAG、SSE、Run Replay 和 Eval Gate，形成一个可观测、可回放、可评测的 LLM 应用工程闭环。

推荐讲解顺序：

1. 服务健康检查
2. PromptHub 管理 prompt
3. RAG 同步问答 + citations
4. RAG 流式 SSE
5. Prompt A/B Compare
6. trace / compare replay
7. 错误契约
8. QA20 Eval Report + strict gate

---

## Day22 Acceptance

* demo 能按上述顺序跑通。
* 每一步都有命令、预期输出和讲解点。
* 不新增大功能，只修 demo 串联中暴露的小问题。
* `pytest -q` 保持全绿。
