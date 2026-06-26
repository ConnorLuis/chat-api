# chat-api 系统设计文档

## 1. 项目概览

`chat-api` 是一个面向工程训练的最小可用 LLM 应用服务。它从一个简单的 FastAPI `/health` 与 `/chat` 接口，逐步演进为一个具备同步聊天、SSE 流式输出、PromptHub、Prompt A/B Compare、Run Replay、Knowledge Base、RAG、评测回归、CI 与可插拔 RAG 后端的完整项目。

这个项目的目标不是只演示“能调用大模型”，而是把一个 LLM 应用从“功能可用”推进到“工程可维护”。它覆盖了一个真实 LLM 应用常见的关键链路：

```text
接口契约
→ 模型供应商抽象
→ 流式输出协议
→ Prompt 管理
→ 运行日志与回放
→ 知识库
→ RAG 上下文注入
→ 评测与回归门槛
→ CI
→ 可插拔 RAG 后端
→ 可观测性
→ 混合检索
→ 可复现评测流程
```

当前项目支持的主要接口：

```text
GET    /health
POST   /chat
POST   /chat/stream
GET    /demo
POST   /prompt/compare
GET    /prompts
GET    /runs/trace/{trace_id}
GET    /runs/compare/{compare_group_id}
POST   /kb/documents
GET    /kb/search
GET    /kb/documents
DELETE /kb/documents/{doc_id}
```

核心能力：

- `provider=mock|ollama` 的可插拔 LLM 引擎；
- 同步 `/chat` 与 SSE `/chat/stream`；
- 结构化 `metadata`、`trace_id`、`latency_ms`；
- PromptHub 与 A/B Compare；
- JSONL 运行日志与回放；
- KB 入库、检索、删除；
- RAG 同步与流式上下文注入；
- citations 证据溯源；
- `RAG_BACKEND=native|langchain` 可插拔 RAG 后端；
- RAG 耗时拆解与可观测性；
- Hybrid RAG：向量检索 + 词面打分 + 融合重排；
- QA20 RAG 评测与 strict regression gates；
- KB seed / eval workflow 脚本化；
- GitHub Actions CI。

---

## 2. 系统架构

### 2.1 总体架构

```text
Client / Demo UI / curl
        |
        v
FastAPI app
        |
        +-- middleware
        |     └── trace_id + latency logging
        |
        +-- /chat
        |     ├── 请求校验
        |     ├── 可选 PromptHub 渲染
        |     ├── 可选 RAG 上下文构建
        |     ├── LLM provider 调用
        |     ├── run log 写入
        |     └── ChatResponse 返回
        |
        +-- /chat/stream
        |     ├── 请求校验
        |     ├── 可选 PromptHub 渲染
        |     ├── 可选 RAG 上下文构建
        |     ├── LLM provider 流式调用
        |     ├── SSE 事件：meta/token/usage/done/error
        |     └── run log 写入
        |
        +-- /prompt/compare
        |     ├── 渲染 Prompt A
        |     ├── 渲染 Prompt B
        |     ├── 两次调用 provider
        |     ├── 对比指标
        |     └── 写入同组 run logs
        |
        +-- /runs/*
        |     └── 查询 JSONL 运行日志
        |
        +-- /kb/*
              ├── 文档存储
              ├── 文本分块
              ├── embedding
              ├── Chroma 向量库
              ├── 检索
              └── tombstone 删除
```

### 2.2 主要模块

```text
src/app/main.py
src/app/api/routes_chat.py
src/app/api/routes_prompt.py
src/app/api/routes_kb.py
src/app/core/settings.py
src/app/core/errors.py
src/app/core/middleware.py

src/app/llm/
├── base.py
├── mock.py
├── ollama.py
└── schemas.py

src/app/prompt/
├── hub.py
└── schemas.py

src/app/runs/
└── store.py

src/app/kb/
├── chunking.py
├── chroma_store.py
├── embeddings.py
├── index_text.py
├── rag_context.py
├── schemas.py
└── store.py

src/app/rag/
├── base.py
├── schemas.py
├── factory.py
├── native_backend.py
└── langchain_backend.py
```

### 2.3 运行时存储

默认运行时目录：

```text
kb/
├── chroma/        # Chroma 持久化向量库
├── docs/          # 按 doc_id 保存的原始 markdown 文档
└── docs.jsonl     # append-only 文档元数据 / tombstone 日志

runs/
└── prompt_runs.jsonl
```

这些目录和文件属于运行时产物，一般不提交到 Git。

### 2.4 配置项

关键环境变量：

```text
OLLAMA_BASE_URL
OLLAMA_MODEL
OLLAMA_TIMEOUT_S

RUN_LOG_PATH

KB_DIR
KB_CHROMA_DIR
KB_COLLECTION
KB_CHUNK_SIZE
KB_CHUNK_OVERLAP
KB_TOP_K
KB_CANDIDATE_K
KB_MAX_CONTEXT_CHARS

RAG_BACKEND=native|langchain

EMBEDDING_PROVIDER=mock|hf
EMBEDDING_MODEL
EMBEDDING_DIM
```

WSL2 访问 Windows Ollama 时使用 Windows 网关 IP：

```bash
WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"
```

---

## 3. `/chat` 同步请求链路

`POST /chat` 是同步聊天接口。它的设计目标是稳定、可测试、可观测，并且在下游 provider 失败时返回结构化错误。

### 3.1 基本流程

```text
Client
  |
  v
POST /chat
  |
  +-- 校验 ChatRequest
  |
  +-- 构建 trace_id
  |
  +-- 解析 provider：mock | ollama
  |
  +-- 解析 prompt_id / prompt_version
  |
  +-- 如果 use_kb=true：
  |       query = 最新 user message
  |       rag_backend = get_rag_backend()
  |       rag_result = rag_backend.build_context(query, top_k)
  |       将 RAG context 注入为 system message
  |
  +-- 调用 LLM engine.generate()
  |
  +-- 构建 ChatResponse
  |
  +-- 写入 run log
  |
  v
Client 接收 JSON 响应
```

### 3.2 响应契约

典型响应结构：

```json
{
  "trace_id": "...",
  "session_id": null,
  "answer": "...",
  "metadata": {
    "provider": "ollama",
    "model": "qwen2.5:7b",
    "latency_ms": 1234,
    "prompt_id": "qa_strict",
    "prompt_version": "v1",
    "rag": {
      "enabled": true,
      "top_k": 3,
      "hits": 3,
      "candidate_k": 50,
      "citations": [],
      "error": null,
      "backend": "native",
      "vectorstore": null,
      "retrieval_mode": "hybrid",
      "fusion": "vector_lexical",
      "vector_weight": 0.7,
      "lexical_weight": 0.3,
      "embedding_ms": 0,
      "retrieval_ms": 10,
      "rerank_ms": 2,
      "context_build_ms": 0,
      "total_ms": 12
    },
    "context_chars": 2000,
    "rag_error": null
  }
}
```

`model` 字段始终是字符串：

```text
真实 provider → 实际模型名
未知或缺失 → "unknown"
```

这样前端和测试都不需要额外处理 `model=null` 的情况。

### 3.3 RAG 降级策略

当 `use_kb=true` 但 KB 为空或 RAG 构建失败时，同步 `/chat` 尽量返回 200，并把 RAG 错误写入：

```text
metadata.rag.error
metadata.rag_error
```

这样可以区分两类问题：

```text
LLM provider 失败 → /chat 返回 HTTP 502
RAG 可选上下文失败 → /chat 尽量降级返回 200
```

---

## 4. `/chat/stream` 流式请求链路

`POST /chat/stream` 使用 Server-Sent Events。它和 `/chat` 共享大部分前置逻辑：请求校验、PromptHub、RAG 上下文构建、provider 选择。区别在于响应以 SSE 事件块形式流式返回。

### 4.1 SSE 事件顺序

正常情况下：

```text
event: meta
data: {...}

event: token
data: ...

event: token
data: ...

event: usage
data: {...}

event: done
data: [DONE]
```

下游失败时：

```text
event: meta
data: {...}

event: error
data: {...}
```

### 4.2 SSE 事件块格式

每个事件块由若干行组成，并以空行结束：

```text
event: <type>
data: <payload>

```

设计约束：

- `data` 必须是字符串；
- dict/list 会先 JSON 序列化；
- 多行 data 会被拆成多条 `data:`；
- 事件块必须用空行分隔；
- 流式错误通过 `event:error` 传递，而不是修改 HTTP status。

### 4.3 为什么流式错误仍是 HTTP 200

SSE 连接一旦建立，服务端通常已经返回 HTTP 200。后续业务失败不能再改变 HTTP status，因此流式接口通过 `event:error` 表达下游错误。

同步接口：

```text
/chat provider failure → HTTP 502 + structured detail
```

流式接口：

```text
/chat/stream provider failure → HTTP 200 + event:error
```

### 4.4 Stream RAG metadata

当 `use_kb=true` 时，RAG 信息会出现在：

```text
meta.rag
usage.rag
error.rag
```

包含字段：

```text
enabled
top_k
hits
context_chars
citations
error
backend
vectorstore
retrieval_mode
fusion
vector_weight
lexical_weight
embedding_ms
retrieval_ms
rerank_ms
context_build_ms
total_ms
```

---

## 5. RAG Pipeline

RAG 是本项目最核心的工程主线。它从最初的 KB ingest/search 演进到 chat/stream context injection，再演进到 v2 的 backend abstraction、observability、Hybrid RAG 与 reproducible eval workflow。

### 5.1 入库流程

```text
POST /kb/documents
  |
  +-- 校验 payload：text/source/title
  |
  +-- extract_index_text()
  |
  +-- split_text(chunk_size, overlap)
  |
  +-- get_embedding_engine(settings)
  |
  +-- 对 chunks 计算 embedding
  |
  +-- upsert chunks 到 Chroma
  |
  +-- 将原始文档保存到 kb/docs/{doc_id}.md
  |
  +-- 将元数据追加到 kb/docs.jsonl
  |
  v
返回 doc_id + chunks + metadata
```

### 5.2 索引文本清洗

KB seed 文档中可能包含给维护者或评测使用的辅助区块，例如：

```text
# Keywords
# QA Seeds
# Appendix
# Changelog
```

这些内容有助于维护文档和构造评测集，但不应该进入向量索引。否则，评测题、关键词或答案提示会污染检索结果，导致系统不是根据正文召回，而是根据 QA Seeds 命中。

因此，`extract_index_text()` 只保留真正要入库的正文部分，并在遇到以下标记时截断：

```text
---
# Keywords
# QA Seeds
# Appendix
# Changelog
```

这个规则解决了 Day19 中遇到的 QA Seeds / Keywords 污染问题，保证向量库只索引项目知识正文。

### 5.3 文本分块

`split_text()` 使用滑窗分块：

```text
chunk_size
chunk_overlap
next_start pointer
```

其中：

- `chunk_size` 控制每个 chunk 的最大长度；
- `chunk_overlap` 保留相邻 chunk 的上下文连续性；
- `next_start` 控制下一块的起点，必须保证持续前进，避免死循环。

滑窗分块的设计目标是让单个 chunk 不至于过长，同时保留跨段落的语义连续性。

### 5.4 检索流程

原始检索流程：

```text
GET /kb/search?q=...&top_k=...
  |
  +-- 对 query 计算 embedding
  |
  +-- 查询 Chroma
  |
  +-- 返回 hits
```

Hit 的结构：

```text
doc_id
chunk_id
score
text
source
title
```

其中：

- `doc_id` 表示文档 ID；
- `chunk_id` 表示 chunk ID；
- `score` 表示向量相似度或检索得分；
- `text` 是命中的 chunk 内容；
- `source` 是来源路径或来源标记；
- `title` 是文档标题。

### 5.5 RAG 上下文构建

Chat RAG 不直接使用原始 top_k，而是先召回更大的候选池，再重排截断：

```text
query
→ candidate_k retrieval
→ rerank_hits()
→ top_k
→ build_rag_context()
→ 注入为 system context
```

重要参数：

```text
KB_CANDIDATE_K = 50
kb_top_k = 请求级最终上下文数量
KB_MAX_CONTEXT_CHARS = 最大注入上下文长度
```

`candidate_k` 可以大于 `top_k`。原因是系统先召回更大的候选池，再通过 rerank 选择最终注入给模型的少量 chunk。这样可以解决“真正相关的 chunk 不在原始向量 top-3，但出现在 top-50”这类问题。

### 5.6 RAGBackend 抽象

v2 引入了统一的 RAG 后端接口：

```text
RAGBackend.build_context(query, top_k) -> RAGContextResult
```

相关文件：

```text
src/app/rag/base.py
src/app/rag/schemas.py
src/app/rag/factory.py
src/app/rag/native_backend.py
src/app/rag/langchain_backend.py
```

引入这个抽象后，route 层不再直接关心 embedding、vector store、rerank 或 context construction 的细节。

route 层只依赖：

```python
rag_backend = get_rag_backend()
rag_result = rag_backend.build_context(query=query, top_k=top_k)
```

后端统一返回：

```text
RAGContextResult
├── context_text
├── citations
└── extra
```

这样可以保证 `/chat` 和 `/chat/stream` 使用同一套 RAG 上下文构建逻辑，同时为 native 和 langchain 两种 backend 保留扩展空间。

### 5.7 Native 后端

Native 后端封装项目原本手写的 RAG 流程：

```text
query
→ get_embedding_engine(settings)
→ Chroma query
→ Hit
→ rerank_hits()
→ build_rag_context()
→ RAGContextResult
```

它的优点是透明、可控、容易调试，适合学习和面试讲解。每一步都能明确解释：query 如何 embedding，Chroma 如何召回，candidate_k 为什么要比 top_k 大，rerank 如何影响最终上下文。

### 5.8 LangChain 后端

LangChain 后端使用 `langchain_chroma.Chroma`，但仍然复用项目自己的 embedding engine：

```text
get_embedding_engine(settings)
→ ProjectEmbeddings
→ langchain_chroma.Chroma
→ similarity_search_with_score()
→ Hit
→ rerank_hits()
→ build_rag_context()
→ RAGContextResult
```

这样设计是为了避免 embedding 空间不一致。如果文档入库时使用项目自己的 embedding engine，而查询时换成另一个 embedding 模型，检索质量会变得不可靠。LangChain 后端通过包装项目 embedding engine，保证文档向量和查询向量处于同一向量空间。

LangChain 依赖是可选依赖：

```text
requirements-langchain.txt
```

基础 CI 不强制安装 LangChain。LangChain 相关测试使用 optional dependency guard，避免污染基础 CI。

### 5.9 RAG 可观测性

RAG 后端会把耗时拆解写入 `RAGContextResult.extra`：

```text
backend
vectorstore
embedding_ms
retrieval_ms
rerank_ms
context_build_ms
total_ms
```

这些字段会透传到：

```text
/chat metadata.rag
/chat/stream meta.rag
/chat/stream usage.rag
/chat/stream error.rag
```

这样可以在 API 响应里直接看到 RAG 每个阶段的耗时，有助于定位性能瓶颈。例如，当引入 Hybrid RAG 后，可以观察 `rerank_ms` 是否明显增长；当切换 LangChain 后端后，可以观察 `retrieval_ms` 与 native 后端的差异。

### 5.10 Hybrid RAG

Day28 将 rerank 升级为轻量 Hybrid RAG：

```text
向量检索
→ 词面打分
→ 融合重排
→ top_k context
```

当前融合配置：

```text
retrieval_mode = "hybrid"
fusion = "vector_lexical"
vector_weight = 0.7
lexical_weight = 0.3
```

融合分数由三部分组成：

```text
1. vector score：向量检索得分；
2. lexical score：词面匹配得分；
3. query-aware rule bonus：已有的查询感知规则加分。
```

词面打分会利用：

```text
query tokens
title
source
text
exact phrase
CJK n-grams
```

Hybrid RAG 对工程类关键词问题更稳定，例如：

```text
docs.jsonl
candidate_k
SSE event block
DELETE /kb/documents/{doc_id}
PromptHub prompt_id/prompt_version
```

这个改动不改变外部请求契约。客户端仍然只需要传 `use_kb` 与 `kb_top_k`。Hybrid 相关信息只作为可观测字段出现在 `metadata.rag` 或 SSE 的 `rag` 字段中。

---

## 6. PromptHub 与 A/B Compare

### 6.1 PromptHub

PromptHub 允许请求通过以下字段选择 prompt 模板：

```text
prompt_id
prompt_version
prompt_vars
```

它的作用是把 prompt 内容从业务路由中解耦出来。这样可以在不改 API 路由的情况下切换 prompt 策略，也方便做 prompt 版本管理、对比实验和回放。

示例 prompt 标识：

```text
chat:v1
qa_strict:v1
```

### 6.2 Prompt 渲染流程

```text
ChatRequest
  |
  +-- prompt_id / prompt_version
  |
  +-- 加载 prompt template
  |
  +-- 渲染 prompt_vars
  |
  +-- prepend 或 merge 到 messages
  |
  v
LLM provider call
```

### 6.3 Prompt A/B Compare

`POST /prompt/compare` 接收同一个用户输入和两套 prompt 配置：

```text
prompt_a
prompt_b
```

它会调用 provider 两次，并返回：

```text
compare_group_id
a.trace_id
b.trace_id
a.answer
b.answer
latency metrics
output length metrics
```

两条运行记录会写入 run log，并共享同一个 `compare_group_id`。

### 6.4 A/B Compare 的意义

Prompt 改动可能影响输出质量、输出长度和延迟。A/B Compare 提供了一种轻量方式，用同一个输入和同一组 provider 参数比较两种 prompt 策略。

结合 run log 和 replay，prompt 实验不再是一次性的临时调用，而是可以被审计、回放和复盘。

---

## 7. Run Log 与 Replay

### 7.1 Run log

运行日志以 JSONL 形式写入：

```text
runs/prompt_runs.jsonl
```

一条记录通常包含：

```text
trace_id
compare_group_id
variant
mode
provider
model
prompt_id
prompt_version
latency_ms
prompt_chars
output_chars
temperature
top_p
max_tokens
created_at
```

JSONL 的好处是 append-only、容易追加、容易用 shell 或 Python 脚本排查。

### 7.2 按 trace_id 回放

```text
GET /runs/trace/{trace_id}
```

返回匹配该 trace ID 的记录。

如果找不到：

```text
HTTP 404
```

### 7.3 按 compare_group_id 回放

```text
GET /runs/compare/{compare_group_id}
```

返回 A/B 两组记录和汇总指标。

### 7.4 Replay 的作用

Replay 主要用于：

```text
debugging
demo
prompt comparison
traceability
post-hoc analysis
```

它把 prompt 实验从一次性调用变成可追踪记录，有助于调试、演示和后续分析。

---

## 8. 错误处理

### 8.1 错误契约目标

本项目把错误处理视为 API contract 的一部分。设计目标是：

```text
1. 明确同步与流式接口的不同行为；
2. 错误结果可被机器解析；
3. 保留 trace_id；
4. 保留 provider/model；
5. 不把原始堆栈直接暴露给客户端。
```

### 8.2 同步接口错误

对于 `/chat`，下游 provider 失败时返回：

```text
HTTP 502 Bad Gateway
```

响应结构：

```json
{
  "detail": {
    "trace_id": "...",
    "provider": "ollama",
    "model": "qwen2.5:7b",
    "latency_ms": 15,
    "error": "ollama failed: ..."
  }
}
```

### 8.3 流式接口错误

对于 `/chat/stream`，HTTP 连接通常已经建立，因此 provider 失败会通过 SSE 事件返回：

```text
event: error
data: {"trace_id":"...","provider":"ollama","model":"qwen2.5:7b","latency_ms":15,"error":"..."}
```

### 8.4 RAG 错误

RAG 是可选上下文。如果 RAG 失败但 provider 仍可回答，`/chat` 和 `/chat/stream` 应尽量降级。RAG 错误会记录在：

```text
metadata.rag.error
metadata.rag_error
```

或 stream 的 `rag.error` 中。

### 8.5 常见运行时问题

在一个终端修改环境变量，不会影响另一个已经运行的 uvicorn 进程。

正确做法：

```bash
# 停止 uvicorn
Ctrl+C

# 在同一个终端 export 环境变量
export OLLAMA_BASE_URL=...

# 重启服务
python -m uvicorn src.app.main:app --reload --port 8000
```

---

## 9. 评测与回归门槛

### 9.1 QA20 评测

RAG 评测使用：

```text
eval/qa_rag_20.jsonl
scripts/eval_qa_rag.py
scripts/build_eval_report.py
```

评测命令：

```bash
python scripts/eval_qa_rag.py   --qa eval/qa_rag_20.jsonl   --out eval/results/rag_eval_20.jsonl   --summary eval/results/rag_eval_20_summary.json   --provider ollama
```

报告生成命令：

```bash
python scripts/build_eval_report.py   --results eval/results/rag_eval_20.jsonl   --summary eval/results/rag_eval_20_summary.json   --out eval/reports/rag_eval_report.md   --strict
```

### 9.2 指标

汇总指标：

```text
answer_hit_rate
citation_hit_rate
effective_rag_rate
title_hit_rate
avg_latency_ms
p50_latency_ms
p95_latency_ms
failed
```

`answer_hit_rate` 检查回答是否命中期望关键词，并拦截“不确定/需要更多上下文”等拒答模式。

`citation_hit_rate` 检查是否存在 citations，且 citation source 是否命中期望来源。

`title_hit_rate` 是诊断指标，用于检查 citation title metadata 是否合理。

`effective_rag_rate` 检查：

```text
rag.enabled == true
rag.hits > 0
context_chars > 0
```

### 9.3 Strict gates

当前 strict gates：

```text
answer_hit_rate >= 0.90
citation_hit_rate >= 0.95
effective_rag_rate >= 0.95
title_hit_rate >= 0.85
p95_latency_ms <= 6000
failed_count == 0
```

### 9.4 Citation matching

Day28 将 citation matching 从脆弱的 exact match 修复为 normalized substring match。

原因是 QA20 中的期望来源可能是类别标记：

```text
expected_sources = ["kb_seed"]
```

而运行时 citation 的实际 source 是完整路径：

```text
actual citation.source = "docs/kb_seed/07_KB Ingest & Search.md"
```

如果使用精确匹配，即使 citation 正确也会被判定为失败。

同时，title matching 支持 source fallback，用来兼容历史 metadata 中 `title="Header"` 这类情况。

### 9.5 可复现 eval workflow

Day29 引入：

```text
scripts/seed_kb.py
scripts/run_rag_eval_workflow.py
```

推荐本地验收流程：

```bash
# 先停止 uvicorn
python scripts/run_rag_eval_workflow.py --reset-runtime --yes

# 重启 uvicorn
WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"
python -m uvicorn src.app.main:app --reload --port 8000

# 运行 workflow
python scripts/run_rag_eval_workflow.py   --provider ollama   --results eval/results/rag_eval_20_day29_workflow.jsonl   --summary eval/results/rag_eval_20_day29_workflow_summary.json   --report eval/reports/rag_eval_report_day29_workflow.md
```

Workflow 步骤：

```text
health check
→ seed KB
→ provider warmup
→ QA20 eval
→ strict report
→ print summary
```

### 9.6 Provider warmup

对于本地 Ollama，第一次请求延迟可能会污染 20 题评测集中的 p95 latency。Day29 在正式评测前增加 provider warmup：

```text
POST /chat
provider = args.provider
use_kb = false
max_tokens = 16
temperature = 0.0
```

warmup 后验证结果：

```text
total = 20
success = 20
failed = 0
answer_hit_rate = 0.90
citation_hit_rate = 1.00
effective_rag_rate = 1.00
title_hit_rate = 0.95
avg_latency_ms = 1495
p50_latency_ms = 1396
p95_latency_ms = 2750
```

---

## 10. 设计取舍

### 10.1 保留 Native RAG，而不是直接替换

Native RAG 透明、可控、容易调试：

```text
embedding
→ Chroma
→ candidate_k
→ rerank
→ context
```

它适合学习和面试讲解，因为每一个阶段都能清楚说明。

### 10.2 把 LangChain 作为可选后端

LangChain 适合作为生态集成入口，但不应该让它主导项目架构。

因此依赖拆分为：

```text
requirements.txt              # 基础服务与 CI 依赖
requirements-langchain.txt    # 可选 LangChain 依赖
```

这样可以避免基础 CI 变慢和变脆弱。

### 10.3 LangChain 后端复用项目 embedding engine

如果文档入库使用一个 embedding 模型，而查询使用另一个 embedding 模型，检索质量会不稳定。LangChain 后端通过包装项目已有的 embedding engine，保证文档向量和查询向量处于同一个向量空间。

### 10.4 保持请求契约稳定

Day24 到 Day29 修改了内部 RAG 架构，但没有要求客户端修改请求字段。

这说明：

```text
内部架构可以演进；
外部 API 保持稳定；
测试保护 contract。
```

### 10.5 先做轻量 Hybrid RAG，而不是重型 reranker

Cross-Encoder reranker 可能提升质量，但会增加延迟和依赖复杂度。当前 strict gate 包含：

```text
p95_latency_ms <= 6000
```

因此 Day28 优先使用轻量词面信号，而不是立即引入重型 reranker。

### 10.6 Ollama QA20 workflow 不放进 CI

QA20 with Ollama 依赖：

```text
本地模型是否可用；
Windows/WSL 网络；
runtime KB 状态；
硬件性能。
```

CI 应保持确定性和快速。因此：

```text
CI → pytest with mock provider / mock embedding
本地验收 → run_rag_eval_workflow.py with ollama
```

---

## 11. 当前边界与未来工作

### 11.1 当前边界

这个项目目前仍是工程训练项目，不是生产级 RAG 平台。

当前边界：

```text
1. 没有认证与鉴权；
2. 没有数据库级文档元数据管理；
3. 没有多租户隔离；
4. 没有分布式 tracing 后端；
5. 没有生产级日志系统；
6. 没有用于入库的后台任务队列；
7. 没有 chunk 级管理 UI；
8. 没有真实 token accounting；
9. 没有 Cross-Encoder reranker；
10. 没有 query rewrite；
11. 没有在线评测 dashboard；
12. 还没有生产部署加固。
```

### 11.2 后续可扩展方向

可能的后续方向：

```text
1. 云端部署；
2. Docker Compose；
3. PostgreSQL 元数据存储；
4. Redis / 后台任务队列；
5. 真实 token accounting；
6. query rewrite；
7. 可选 Cross-Encoder reranker；
8. hybrid retrieval 参数调优；
9. RAG eval dashboard；
10. LangGraph Agent 层；
11. MCP 工具集成；
12. 认证与用户级 KB。
```

### 11.3 Day30 收口建议

v2 收口阶段，最有价值的工作不是继续堆新功能，而是文档和演示包装：

```text
1. 最终 README / HANDOFF；
2. v2 demo guide；
3. system design 文档；
4. 面试讲解稿；
5. 最终验收命令。
```

最终验收命令应包括：

```bash
pytest -q

python scripts/run_rag_eval_workflow.py --reset-runtime --yes
# 重启 uvicorn
python scripts/run_rag_eval_workflow.py --provider ollama
```

这条链路能讲清楚：

```text
tests 保护本地 contract；
workflow 验证 RAG 质量与回归门槛；
CI 保护分支稳定性；
system_design 解释架构与设计取舍。
```
