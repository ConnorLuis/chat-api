# chat-api

一个最小可用的 FastAPI 聊天服务（工程化训练用），支持：

* `GET /health`：健康检查
* `POST /chat`：同步聊天（`provider=mock|ollama`），返回 `metadata`
* `POST /chat/stream`：SSE 流式聊天（`provider=mock|ollama`），事件：`meta/token/usage/done/error`
* 全局中间件：`x-trace-id` + latency 日志
* 可插拔 LLM 引擎：mock / ollama
* RAG：KB 入库/检索、同步/流式上下文注入、citations 溯源
* KB 管理：文档列表、软删除 tombstone、Chroma 向量清理
* RAG 评测：QA20 离线评测、answer/citation/effective_rag/latency 指标、Markdown report + regression gates
* pytest：基础回归 + SSE 契约测试 + 错误契约测试 + RAG 评测回归测试

---

## Requirements

* Python 3.10+
* 推荐：WSL2 Ubuntu + conda
* 可选：Windows 安装 Ollama（用于本地大模型）

---

## Quick Start

### 1) Activate env & install deps

```bash
conda activate chatapi
python -m pip install -U fastapi uvicorn httpx pydantic pytest
```

### 2) Run server

```bash
cd ~/projects/chat-api
python -m uvicorn src.app.main:app --reload --port 8000
```

### 3) Health check

```bash
curl http://localhost:8000/health
```

---

## Environment variables

* `OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
* `OLLAMA_MODEL` (default: `qwen2.5:7b`)
* `OLLAMA_TIMEOUT_S` (default: `60`)
* `RUN_LOG_PATH` (default: `runs/prompt_runs.jsonl`)
* `KB_DIR` (default: `kb`)
* `KB_CHROMA_DIR` (default: `${KB_DIR}/chroma`)
* `KB_TOP_K` (default: `5`)
* `KB_CANDIDATE_K` (default: `50`)：先召回更大候选池，再 rerank 截断到 `kb_top_k`
* `EMBEDDING_PROVIDER` (default: `mock`, options: `mock|hf`)
* `EMBEDDING_MODEL`：HF embedding 模型名或本地路径

### WSL2 -> Windows Ollama

如果 Ollama 安装在 Windows，WSL 需要用 Windows 网关 IP 访问：

```bash
WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"
```

---

## API: Sync Chat

### Sync chat (mock)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"provider":"mock","messages":[{"role":"user","content":"hi"}]}' | cat
```

Example response（稳定契约字段）：

```json
{
  "trace_id": "...",
  "session_id": null,
  "answer": "...",
  "metadata": {
    "provider": "mock",
    "model": "unknown",
    "latency_ms": 0
  }
}
```

### Sync chat (ollama)

确保 Windows 侧有模型：

```powershell
ollama pull qwen2.5:7b
```

调用：

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"provider":"ollama","messages":[{"role":"user","content":"一句话解释RAG"}],"max_tokens":128}' | cat
```

---

## API: Streaming (SSE)

`POST /chat/stream` 返回 **SSE (Server-Sent Events)**，响应头：

* `Content-Type: text/event-stream`

### Event types

* `meta`  : 初始化信息（至少 `trace_id/provider/model`）
* `token` : 增量输出 token/chunk
* `usage` : 统计信息（`trace_id/provider/model/latency_ms/token_events`）
* `done`  : 流式结束（`[DONE]`）
* `error` : 结构化错误（`trace_id/provider/model/latency_ms/error`）

### Example

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"provider":"ollama","messages":[{"role":"user","content":"一句话解释RAG"}],"max_tokens":128}'
```

---

## Error Handling Contract

### Sync `/chat` error contract (HTTP 502)

同步接口下游失败用 **HTTP 502 Bad Gateway** 表达，并在 body 的 `detail` 中返回可机器解析的结构化错误。

示例（强制下游失败）：

```bash
# 注意：必须影响“服务进程”（见下方备注）
export OLLAMA_BASE_URL=http://127.0.0.1:1

curl -i -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"provider":"ollama","messages":[{"role":"user","content":"hi"}]}'
```

示例响应：

```json
{
  "detail": {
    "trace_id": "f519bbe1-550c-41f3-a3ac-957a1e6dd94e",
    "provider": "ollama",
    "model": "qwen2.5:7b",
    "latency_ms": 15,
    "error": "ollama failed: [Errno 111] Connection refused"
  }
}
```

### Streaming `/chat/stream` error contract (SSE `event:error`)

流式接口通常会先建立 SSE 通道（HTTP 200），**业务失败通过 `event:error` 传递**。

示例（强制下游失败）：

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:1

curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"provider":"ollama","messages":[{"role":"user","content":"hi"}],"max_tokens":8}'
```

示例输出：

```text
event: meta
data: {"trace_id":"293e7c41-80a4-4c96-9d10-e9c22129b8bb","provider":"ollama","model":"qwen2.5:7b"}

event: error
data: {"trace_id":"293e7c41-80a4-4c96-9d10-e9c22129b8bb","provider":"ollama","model":"qwen2.5:7b","latency_ms":8,"error":"ollama failed: All connection attempts failed"}
```

### Model field guarantee

为了让前端更省事、契约更硬：`model` **始终是字符串**（不会是 null）：

* 真实 provider：实际模型名（如 `qwen2.5:7b`）
* 未知/缺失：`"unknown"`

适用范围：

* `/chat` 的 `metadata.model`
* `/chat/stream` 的 `meta / usage / error` 事件

---

## SSE event format（补充说明）

每个 SSE “事件块”都遵循以下格式，并以**空行结束**：

```text
event: <type>
data: <string-or-json>

```

说明：

* `data:` 必须是字符串；如果你传的是 dict/list，会先做 JSON 序列化再输出
* `data` 支持多行（会拆成多条 `data:` 行），但同一个事件块仍以空行结束

---

## Runtime debugging（运行时调试）

### 1) 看日志（推荐关注这些字段）

每条请求相关日志建议至少包含：

* `trace_id`
* `provider`
* `model`
* `latency_ms`

当你排障时：

* 先用响应头/响应体拿到 `trace_id`
* 再用 `trace_id` 在日志里定位整条链路

### 2) 常见坑：修改 env 后需要重启服务

`export OLLAMA_BASE_URL=...` 只会影响**当前 shell 启动的进程**。
如果 uvicorn 已经在另一个终端运行，你在新终端里 `export` 不会影响正在跑的服务。

正确做法：

* 在**启动 uvicorn 的那个终端**里 export，再重启服务；或
* 停掉 uvicorn（Ctrl+C）后，在同一终端 export，再启动

---

## Tests

```bash
pytest -q
```

---

## Troubleshooting

* WSL 访问不到 `127.0.0.1:11434`：使用 `/etc/resolv.conf` 的 nameserver IP 作为 Windows 网关，并设置 `OLLAMA_BASE_URL`
* `/api/tags` 返回 `{"models":[]}`：说明还没 pull 模型（Windows 执行 `ollama pull qwen2.5:7b`）

---

---

## Demo（Streaming SSE）

启动服务后，打开：

- `http://localhost:8000/demo`

功能：
- 选择 provider：`mock`（测试）/ `ollama`（本地模型）
- 输入 prompt，点击 Start 开始流式输出
- 页面展示：meta（trace_id/provider/model）、output（token 拼接）、usage、error、done

实现要点：
- Demo 使用 `fetch(POST /chat/stream)` 并读取 `ReadableStream` 解析 SSE（因为 `EventSource` 仅支持 GET）
- SSE 事件块用 `\n\n` 分隔；每块包含 `event:` 与 `data:` 行


### Stop / Abort（Day12）

Demo 现在支持 **Stop** 按钮中断流式请求（使用 `AbortController` + `fetch(..., { signal })`）：

- 点击 **Stop** 会触发 `controller.abort()`，前端立即停止读取流并恢复按钮状态
- `AbortError` 属于“用户主动取消”，不会显示为业务错误（Error 区不会红）
- Stop 后可以直接再次 Start，开始新一轮流式请求（新的 trace_id）

> 说明：当前后端 `event: usage` 主要包含 `latency_ms` 与 `token_events`；如需 `prompt_tokens/completion_tokens` 可在后端增加真实 token 统计后再展示。



---

## Prompt Compare (Day14)

新增接口：`POST /prompt/compare`  
同一输入套用两套 Prompt（A/B），返回并列结果与对比指标，并将两条运行记录写入 run log（JSONL）用于回放。

### Example

```bash
curl -s -X POST http://localhost:8000/prompt/compare   -H "Content-Type: application/json"   -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"解释介绍RAG"}],
    "max_tokens":128,
    "temperature":0.7,
    "top_p":0.9,
    "prompt_a":{"prompt_id":"chat","prompt_version":"v1","prompt_vars":{}},
    "prompt_b":{"prompt_id":"qa_strict","prompt_version":"v1","prompt_vars":{}}
  }' | cat
```

返回结构（关键字段）：
- `compare_group_id`
- `a/b.trace_id`
- `a/b.metadata`（含 `prompt_id/prompt_version/provider/model/latency_ms`）
- `metrics`（`latency_ms_*`、`output_chars_*`）

### Run log (JSONL)

默认日志：`runs/prompt_runs.jsonl`  
compare 每次写两条（A/B），字段包含：
- `compare_group_id`、`variant`、`mode=compare`
- `trace_id`、`provider/model`
- `prompt_id/prompt_version`
- `latency_ms`、`prompt_chars`、`output_chars`
- `temperature/top_p/max_tokens`

### Replay (offline)

脚本：`scripts/replay_compare.py`

```bash
python scripts/replay_compare.py <compare_group_id>
# 或覆盖日志路径
python scripts/replay_compare.py <compare_group_id> --log ./runs/prompt_runs.jsonl
```

---

## Demo（Stream / Compare）

打开：
- `http://localhost:8000/demo`

支持两种模式：
- **Stream Chat（SSE）**：调用 `/chat/stream`
- **Prompt Compare（A/B）**：调用 `/prompt/compare`

Compare 模式会展示：
- group_id
- A/B 输出并列
- metrics（latency/output diff）
并支持 Copy Curl 复现 compare 请求。

---

## PromptHub Query APIs (Day15)

Day15 将 PromptHub 从“可用”升级为“可查询系统”，新增 3 个接口：

### 1) List prompts

```bash
curl -s http://localhost:8000/prompts | cat
```

返回示例（结构）：

```json
{"prompts":{"chat":["v1","v2"],"qa_strict":["v1"]}}
```

### 2) Replay by trace_id

```bash
curl -s http://localhost:8000/runs/trace/<trace_id> | cat
```

* 找不到：HTTP 404
* 返回包含 `records` 与 `bad_lines`

### 3) Replay compare by compare_group_id

```bash
curl -s http://localhost:8000/runs/compare/<compare_group_id> | cat
```

返回包含：
- `records`（按 A/B 排序）
- `summary`（latency/output diff）
- `bad_lines`

---

### RUN_LOG_PATH（测试/调试）

默认写入：`runs/prompt_runs.jsonl`  
你可以通过环境变量覆盖：

```bash
export RUN_LOG_PATH=/tmp/prompt_runs.jsonl
```

注意：环境变量只影响**启动服务的那个进程**；修改后需要重启 uvicorn 才会生效。

---

## Knowledge Base (RAG Day16)

新增 KB 模块，完成 RAG 的“检索最小闭环”（Index + Retrieve）。

### 1) Ingest document

```bash
curl -s -X POST http://localhost:8000/kb/documents \
  -H "Content-Type: application/json" \
  -d '{"title":"t","source":"manual","text":"RAG 是 Retrieval-Augmented Generation，用于检索增强生成。"}' | cat
```

返回包含：`doc_id`、`chunks`、`metadata.trace_id/latency_ms`。

### 2) Search (topK)

```bash
curl -s "http://localhost:8000/kb/search?q=RAG&top_k=3" | cat
```

返回结构（关键字段）：
- `hits[]`: `doc_id/chunk_id/score/text/source/title`
- `metadata.trace_id/latency_ms`

### KB Environment variables

* `KB_DIR` (default: `kb`)
* `KB_CHROMA_DIR` (default: `${KB_DIR}/chroma`)
* `KB_COLLECTION` (default: `kb_chunks`)
* `KB_CHUNK_SIZE` (default: `800`)
* `KB_CHUNK_OVERLAP` (default: `120`)
* `KB_TOP_K` (default: `5`)
* `EMBEDDING_PROVIDER` (default: `mock`, options: `mock|hf`)
* `EMBEDDING_MODEL` (hf provider)
* `EMBEDDING_DIM` (mock provider)

### Notes
- 测试默认使用 `EMBEDDING_PROVIDER=mock`（稳定、无外部下载）。
- 如需真实语义检索演示，可切换为 `EMBEDDING_PROVIDER=hf` 并设置 `EMBEDDING_MODEL`（会下载/加载模型，首次较慢）。

---

## RAG Chat (Day17)

同步 `/chat` 支持检索增强（RAG），通过 KB topK 检索结果注入上下文，并返回结构化 citations。

### Request fields

在 `/chat` 的请求体中新增可选字段：

- `use_kb` (bool, default: false)
- `kb_top_k` (int, optional)

当 `use_kb=true`：
- 先调用 KB 检索（Chroma topK）
- 将 hits 作为 context 注入 system prompt
- 在响应 `metadata.rag` 中返回 `citations`（doc_id/chunk_id/source/title）

### Example

```bash
# 先入库（Day16）
curl -s -X POST http://localhost:8000/kb/documents \
  -H "Content-Type: application/json" \
  -d '{"text":"RAG 是 Retrieval-Augmented Generation，用于检索增强生成。","source":"manual"}' | cat

# 再调用 /chat(use_kb=true)
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"mock",
    "messages":[{"role":"user","content":"什么是RAG？"}],
    "use_kb": true,
    "kb_top_k": 3
  }' | cat
```

响应 `metadata` 中会包含：

- `metadata.rag.enabled`
- `metadata.rag.top_k`
- `metadata.rag.hits`
- `metadata.rag.citations[]`

---

## RAG Streaming (Day18)

`POST /chat/stream` 支持 RAG（检索增强生成）：请求体新增 `use_kb` / `kb_top_k`。当 `use_kb=true` 时：先 KB topK 检索 → 将命中 chunks 作为 context 注入 system prompt → 流式输出答案。

### Stream RAG fields

SSE 事件中会携带 `rag`：
- `meta.data.rag`: `enabled/top_k/hits/context_chars`
- `usage.data.rag`: `enabled/top_k/hits/context_chars/citations/error`
- `error.data.rag`（若下游失败）: `enabled/top_k/hits/context_chars/citations_count/error`

### Example

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"RAG 的最小闭环包括哪些步骤？"}],
    "prompt_id":"chat","prompt_version":"v1",
    "use_kb": true, "kb_top_k": 3,
    "max_tokens": 128
  }'
```

---

## KB Documents Management (Day18)

新增 KB 管理接口：

### 1) List documents

```bash
curl -s "http://localhost:8000/kb/documents?limit=50&offset=0" | cat
curl -s "http://localhost:8000/kb/documents?include_deleted=true" | cat
```

### 2) Delete a document

```bash
curl -s -X DELETE "http://localhost:8000/kb/documents/<doc_id>" | cat
```

删除行为：Chroma 删除（where doc_id）+ 删除 `docs/<doc_id>.md`（若存在）+ `docs.jsonl` 追加 tombstone（deleted=true）。

---

## Demo RAG (Day18)

`/demo` 增强：
- RAG 开关 + top_k 输入框
- 同步/流式均支持 citations 展示
- 修复 SSE 解析（CRLF/data: 兼容 + 只解析完整块）
- Copy Curl 输出 bash 续行 `\`（避免字面量 `\n` 引起 curl 报错）

---

## Tests (Day18)

新增 Day18 契约测试：
- Demo：RAG UI 关键字存在（可演示能力锁死）
- Stream：RAG meta/usage/done 顺序与 rag.citations 结构锁死（含 KB 空降级）
- KB：documents list/delete 行为锁死（含 include_deleted）

当前：

```bash
pytest -q
# 30 passed
```

---

## RAG Evaluation (Day19)

Day19 将 RAG 从“功能可用”推进到“可量化、可回放、可回归”的评测闭环。

### What was added

- `docs/kb_seed/01-11`：项目知识库种子文档。
- `src/app/kb/index_text.py`：统一索引文本抽取，避免 `Keywords/QA Seeds/Appendix/Changelog` 污染向量库。
- `eval/qa_rag_20.jsonl`：20 条 QA 评测集。
- `scripts/eval_qa_rag.py`：离线评测脚本。
- `src/app/kb/rag_context.py`：`build_rag_context()` + query-aware `rerank_hits()`。
- `KB_CANDIDATE_K=50`：先召回候选池，再基于 query/title/text 做轻量 rerank。

### KB Seed structure

每篇 `docs/kb_seed/*.md` 统一结构：

```md
正文（会入库）
---
# Keywords（只给人看，不入库）
# QA Seeds（只给评测/维护，不入库）
```

入库时 `extract_index_text()` 只保留正文。截断规则：

- 优先遇到独立一行 `---` 截断；
- 如果没有 `---`，遇到一级标题 `# Keywords`、`# QA Seeds`、`# Appendix`、`# Changelog` 截断。

### Run evaluation

```bash
python scripts/eval_qa_rag.py \
  --qa eval/qa_rag_20.jsonl \
  --out eval/results/rag_eval_20.jsonl \
  --summary eval/results/rag_eval_20_summary.json \
  --provider ollama
```

输出：

- `eval/results/rag_eval_20.jsonl`：逐题证据，包含 `qid/question/answer/trace_id/rag/citations/answer_score/citation_score/effective_rag/latency_ms`。
- `eval/results/rag_eval_20_summary.json`：汇总指标。

### Metrics

- `answer_hit_rate`：关键词命中，并且回答没有“不确定/需要更多上下文”等拒答模板。
- `citation_hit_rate`：有 citations，且 citation.source 命中 expected_sources。
- `title_hit_rate`：诊断指标，citation.title 是否命中 expected_titles。
- `effective_rag_rate`：`rag.enabled=true && rag.hits>0 && context_chars>0`。
- `avg/p50/p95 latency_ms`：来自 `/chat` 返回的 metadata。

### Final Day19 result

```text
total = 20
success = 20
failed = 0
answer_hit_rate = 95.0%
citation_hit_rate = 100.0%
effective_rag_rate = 100.0%
avg_latency_ms ≈ 1953ms
```

### Regression tests

Day19/Day20 补充了 3 个关键回归测试：

- `tests/kb/test_index_text.py`：锁死 `extract_index_text` 防污染规则。
- `tests/eval/test_eval_metrics_unit.py`：锁死 uncertain answer guard 与 citation/title 分层口径。
- `tests/kb/test_rag_rerank.py`：锁死 query-aware rerank，防止 RAG 文档全局吸走召回。

---

## RAG Evaluation Report & Regression Gates (Day20)

Day20 将 Day19 的 RAG QA20 离线评测结果整理成 Markdown 报告，并增加回归门槛。

### Generate report

```bash
python scripts/build_eval_report.py \
  --results eval/results/rag_eval_20.jsonl \
  --summary eval/results/rag_eval_20_summary.json \
  --out eval/reports/rag_eval_report.md \
  --strict
```

成功输出：

```text
Report generated: eval/reports/rag_eval_report.md
All regression gates passed!
```

### Current QA20 result

- answer_hit_rate: 95.0%
- citation_hit_rate: 100.0%
- effective_rag_rate: 100.0%
- title_hit_rate: 95.0%
- failed: 0
- p95_latency_ms: 3857ms（低于 6000ms gate）

### Regression gates

- answer_hit_rate >= 0.90
- citation_hit_rate >= 0.95
- effective_rag_rate >= 0.95
- title_hit_rate >= 0.85
- failed_count == 0
- p95_latency_ms <= 6000

### Added KB Seed docs

Day20 新增两篇 KB Seed 源文档：

- `docs/kb_seed/12_RAG Eval Report & Regression Gates.md`
- `docs/kb_seed/13_Retrieval Rerank & Candidate Pool.md`

建议先提交源文档，不急着立刻入库；如果后续把 12/13 纳入 Chroma，需要重新跑 QA20 回归，观察新增文档是否影响召回分布。

---
---

## RAG Evaluation Report & Regression Gates (Day20)

Day20 将 Day19 的 RAG QA20 离线评测结果整理成 Markdown 报告，并增加回归门槛。

### Generate report

```bash
python scripts/build_eval_report.py \
  --results eval/results/rag_eval_20.jsonl \
  --summary eval/results/rag_eval_20_summary.json \
  --out eval/reports/rag_eval_report.md \
  --strict
```

成功输出：

```text
Report generated: eval/reports/rag_eval_report.md
All regression gates passed!
```

### Current QA20 result

- answer_hit_rate: 95.0%
- citation_hit_rate: 100.0%
- effective_rag_rate: 100.0%
- title_hit_rate: 95.0%
- failed: 0
- p95_latency_ms: 3857ms（低于 6000ms gate）

### Regression gates

- answer_hit_rate >= 0.90
- citation_hit_rate >= 0.95
- effective_rag_rate >= 0.95
- title_hit_rate >= 0.85
- failed_count == 0
- p95_latency_ms <= 6000

### Added KB Seed docs

Day20 新增两篇 KB Seed 源文档：

- `docs/kb_seed/12_RAG Eval Report & Regression Gates.md`
- `docs/kb_seed/13_Retrieval Rerank & Candidate Pool.md`

建议先提交源文档，不急着立刻入库；如果后续把 12/13 纳入 Chroma，需要重新跑 QA20 回归，观察新增文档是否影响召回分布。

---

## Demo Storyline (Day21)

Day21 不新增后端接口，也不修改核心业务逻辑，而是把已有能力整理成一条 Day22 可演示故事线：

```text
Health
→ PromptHub
→ RAG Sync Chat
→ RAG Streaming SSE
→ Prompt A/B Compare
→ Replay
→ Error Demo
→ Eval Report
```

演示文档：

- `docs/demo_storyline_day22.md`

该文档包含每一步的命令、预期输出和讲解点，方便在面试或复盘时按顺序展示完整 LLM 应用工程闭环。

Day21 不需要新增契约测试，因为没有改变 API contract、schema、RAG 行为或运行时逻辑；仅通过现有回归测试确认系统未受影响：

```bash
pytest -q
# 44 passed
```

---

## Demo Storyline Run-through (Day22)

Day22 按 `docs/demo_storyline_day22.md` 对完整 demo 链路做了实跑验收。

### Demo flow

```text
/health
→ /prompts
→ /chat + RAG
→ /chat/stream + RAG
→ /prompt/compare
→ /runs/trace/{trace_id}
→ /runs/compare/{compare_group_id}
→ Error Demo
→ build_eval_report.py --strict
```

### Verified results

- `/health` 返回 `{"status":"ok"}`。
- `/prompts` 能列出 `qa_strict:v1` 与 `chat:v1`。
- RAG Sync Chat 能回答 `docs.jsonl 的作用是什么？`，并返回 `KB Ingest & Search` citations。
- RAG Streaming SSE 输出 `meta → token* → usage → done`，usage 中包含 `RAG in Chat/Stream` citations。
- Prompt A/B Compare 返回 `compare_group_id`、A/B trace_id、latency/output diff。
- Replay 支持按 trace_id 单条回放，也支持按 compare_group_id 聚合回放 A/B。
- Error Demo 验证：
  - `/chat` 下游失败 → HTTP 502 + structured detail。
  - `/chat/stream` 下游失败 → HTTP 200 + `event:error`。
- Eval Report strict gate 通过。
- 恢复正常 Ollama 后 `/chat` 可用。
- `pytest -q` 全绿：44 passed。

### Day22 live KB note

Day22 一开始 live KB 里只剩 demo 文档，导致 `docs.jsonl` 问题回答“不确定”。  
解决方式是重新入库 01-11 kb_seed，并保持 12/13 暂不入库，避免改变 QA20 召回分布。

这也验证了 Day19 的核心修复：

```text
raw /kb/search top5 不一定最准确；
/chat 会走 candidate_k=50 + query-aware rerank；
最终注入 context 的是更符合 query 的 top_k chunks。
```

演示结束后，运行时产物已还原：

```bash
git restore kb/chroma kb/docs.jsonl kb/docs
```

---

## Git hygiene

以下是运行时产物，不建议提交：

```gitignore
kb/chroma/
kb/docs/
kb/docs.jsonl
eval/results/
eval/reports/
eval/kb_seed_manifest.jsonl
backup_kb_reset/
```

建议提交：

- `src/**` 源码；
- `docs/kb_seed/*.md` 源文档；
- `docs/demo_storyline_day22.md` 演示脚本；
- `eval/qa_rag_20.jsonl` 评测集；
- `scripts/eval_qa_rag.py` / `scripts/build_eval_report.py`；
- `tests/**` 回归测试；
- README / HANDOFF / day logs / weekly summaries。
