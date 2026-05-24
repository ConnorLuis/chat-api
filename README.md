# chat-api

一个最小可用的 FastAPI 聊天服务（工程化训练用），支持：

* `GET /health`：健康检查
* `POST /chat`：同步聊天（`provider=mock|ollama`），返回 `metadata`
* `POST /chat/stream`：SSE 流式聊天（`provider=mock|ollama`），事件：`meta/token/usage/done/error`
* 全局中间件：`x-trace-id` + latency 日志
* 可插拔 LLM 引擎：mock / ollama
* pytest：基础回归 + SSE 契约测试 + 错误契约测试

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
