# chat-api v2 面试讲解稿

## 0. 使用方式

这份文档不是命令手册，而是面试时的“讲解话术”。建议配合以下文档使用：

```text
docs/system_design.md      # 系统架构与设计取舍
docs/v2_demo_guide.md      # 演示命令手册
HANDOFF.md                 # 项目进度交接
README.md                  # 项目能力概览
```

面试时建议按三层讲：

```text
1. 先用 1 分钟讲清楚项目是什么；
2. 再用 3-5 分钟讲清楚系统架构和 RAG 链路；
3. 最后结合排障案例、评测指标、CI 和设计取舍体现工程能力。
```

---

## 1. 项目一句话介绍

### 1.1 30 秒版本

`chat-api` 是我为了训练 LLM 应用工程能力做的一个 FastAPI 项目。它不是只做一个简单的大模型调用接口，而是从同步聊天、SSE 流式输出、PromptHub、A/B Compare、Run Replay，一直扩展到知识库 RAG、可插拔 RAG backend、Hybrid RAG、QA20 评测回归和 CI。整个项目重点是把一个 LLM 应用从“能跑”推进到“可测试、可观测、可评测、可回归”。

### 1.2 1 分钟版本

这个项目叫 `chat-api`，本质上是一个最小可用但工程链路完整的 LLM 应用服务。底层是 FastAPI，模型层支持 `mock` 和本地 `ollama`，接口层支持同步 `/chat` 和 SSE `/chat/stream`。在此基础上，我做了 PromptHub、Prompt A/B Compare、运行日志、trace 回放、知识库入库检索、RAG 同步和流式问答。

v2 阶段我重点升级了 RAG 架构：把原本写在 route 层的 RAG 逻辑抽象成 `RAGBackend`，支持 `native` 和 `langchain` 两种后端；增加了 RAG timing 可观测性；把 rerank 升级为 Hybrid RAG，也就是向量检索加词面匹配再融合重排；最后做了 `seed_kb.py` 和 `run_rag_eval_workflow.py`，让 QA20 评测可以一键 seed、eval、生成 strict report。

### 1.3 3 分钟版本

我做这个项目的目标是补足 LLM 应用工程能力，而不是只停留在“调一个 API”。所以我按照真实 LLM 应用会遇到的问题逐步推进。

第一阶段是基础服务能力：FastAPI 的 `/health`、`/chat`、`/chat/stream`，支持 `mock` 和 `ollama` 两种 provider。同步接口返回结构化 JSON，流式接口使用 SSE，并定义了 `meta/token/usage/done/error` 事件。

第二阶段是 Prompt 工程能力：我做了 PromptHub，可以通过 `prompt_id` 和 `prompt_version` 管理 prompt；又做了 Prompt A/B Compare，同一个输入可以分别跑两套 prompt，并记录 latency、output length 等指标；所有运行记录会写入 JSONL，后续可以通过 `trace_id` 或 `compare_group_id` 回放。

第三阶段是 RAG：我实现了 KB 入库、分块、embedding、Chroma 检索、RAG 上下文注入和 citations 溯源。后来又补了 QA20 评测集、评测脚本、Markdown 报告和 strict regression gates。

第四阶段是 v2 架构升级：我把 RAG 逻辑从 route 层抽出来，做成 `RAGBackend` 抽象，支持原生实现和 LangChain Chroma 后端。为了能比较和排查性能，我增加了 `embedding_ms/retrieval_ms/rerank_ms/context_build_ms/total_ms` 这些可观测字段。之后又把 rerank 升级为 Hybrid RAG，融合 vector score、lexical score 和 query-aware rule bonus。

最后，我把 Day28 中暴露出的手工评测不稳定问题脚本化：`seed_kb.py` 固定 seed 文档、source 和 title；`run_rag_eval_workflow.py` 串联 health check、seed KB、provider warmup、QA20 eval 和 strict report。最终 QA20 结果是 answer_hit_rate 90%、citation_hit_rate 100%、effective_rag_rate 100%、title_hit_rate 95%、p95 latency 2750ms，strict gate 通过。

---

## 2. 为什么做这个项目

这个项目的训练目标有三个：

```text
1. 熟悉 LLM 应用后端工程链路；
2. 掌握 RAG 从入库、检索、上下文注入到评测回归的完整闭环；
3. 形成面试中可讲、可演示、可复盘的工程项目。
```

我没有直接从 LangChain 或 Agent 框架开始堆功能，而是先手写一个可控的基础系统。这样做有几个好处：

```text
1. 能理解每个模块到底做了什么；
2. 遇到问题能从接口、日志、存储、检索、评测逐层定位；
3. 后续接入 LangChain、LangGraph 或 MCP 时，不会只会调封装；
4. 面试时可以讲清楚系统设计和工程取舍。
```

---

## 3. 系统整体架构怎么讲

### 3.1 架构总览

可以这样讲：

```text
Client / Demo / curl
        |
        v
FastAPI
        |
        +-- /chat                 同步聊天
        +-- /chat/stream          SSE 流式聊天
        +-- /prompt/compare       Prompt A/B Compare
        +-- /prompts              PromptHub 查询
        +-- /runs/*               运行日志回放
        +-- /kb/*                 知识库入库、检索、删除
        |
        +-- LLM Engine            mock / ollama
        +-- RAGBackend            native / langchain
        +-- KB Store              docs.jsonl + docs/*.md
        +-- Vector Store          Chroma
        +-- Eval Workflow         QA20 + strict gates
```

### 3.2 模块拆分

项目主要分成几层：

```text
API 层：
  routes_chat.py
  routes_prompt.py
  routes_kb.py

模型层：
  llm/base.py
  llm/mock.py
  llm/ollama.py

Prompt 层：
  prompt/hub.py

日志与回放：
  runs/store.py

KB / RAG 层：
  kb/chunking.py
  kb/embeddings.py
  kb/chroma_store.py
  kb/rag_context.py
  rag/native_backend.py
  rag/langchain_backend.py

评测层：
  eval/qa_rag_20.jsonl
  scripts/eval_qa_rag.py
  scripts/build_eval_report.py
  scripts/seed_kb.py
  scripts/run_rag_eval_workflow.py
```

### 3.3 设计重点

可以强调：

```text
1. API contract 稳定；
2. provider 可插拔；
3. RAG 逻辑从 route 层解耦；
4. sync 和 stream 共用同一套 RAGBackend；
5. 每个关键能力都有测试保护；
6. CI 跑轻量 deterministic tests；
7. Ollama QA20 作为本地验收 workflow。
```

---

## 4. `/chat` 同步接口怎么讲

`/chat` 是同步接口，主要流程是：

```text
接收 ChatRequest
→ 生成 trace_id
→ 解析 provider
→ 可选渲染 PromptHub
→ 如果 use_kb=true，构建 RAG context
→ 调用 LLM engine
→ 组装 ChatResponse
→ 写入 run log
```

它返回：

```text
trace_id
answer
metadata.provider
metadata.model
metadata.latency_ms
metadata.rag
```

### 面试表述

我会把同步 `/chat` 设计成稳定契约接口。它不仅返回 answer，还返回 metadata，包括 provider、model、latency_ms 和 RAG 信息。这样前端、测试和后续观测都可以依赖这些结构化字段。

另外我保证 `model` 始终是字符串，比如真实模型名或者 `"unknown"`，这样避免前端额外处理 null。

### 错误处理

同步接口下游 provider 失败时返回：

```text
HTTP 502
detail.trace_id
detail.provider
detail.model
detail.latency_ms
detail.error
```

可以讲：

```text
我没有直接把异常栈抛给用户，而是封装成结构化错误。这样既方便前端处理，也方便通过 trace_id 查日志。
```

---

## 5. `/chat/stream` 流式接口怎么讲

`/chat/stream` 使用 SSE。事件顺序是：

```text
event: meta
event: token
event: token
...
event: usage
event: done
```

下游失败时：

```text
event: meta
event: error
```

### 面试表述

流式接口的重点是协议稳定。SSE 每个事件块用空行分隔，`data` 必须是字符串。如果传 dict/list，会先 JSON 序列化。

同步接口失败可以返回 HTTP 502，但 SSE 一旦建立连接通常已经是 HTTP 200，所以流式接口的业务错误要通过 `event:error` 传递。这是同步和流式错误契约的核心差异。

可以强调的工程点：

```text
1. SSE 事件块格式测试；
2. meta/token/usage/done/error 顺序测试；
3. stream error 不改 HTTP status；
4. 前端 demo 使用 fetch + ReadableStream 解析 SSE，而不是 EventSource，因为 EventSource 只支持 GET。
```

---

## 6. PromptHub 和 A/B Compare 怎么讲

### 6.1 PromptHub

PromptHub 用于通过：

```text
prompt_id
prompt_version
prompt_vars
```

管理 prompt 模板。

可以这样讲：

```text
我不希望 prompt 散落在业务代码里，所以做了 PromptHub。请求可以指定 prompt_id 和 prompt_version，服务端负责渲染模板。这样 prompt 版本可以管理，也方便做后续对比实验。
```

### 6.2 A/B Compare

`/prompt/compare` 对同一输入运行两套 prompt：

```text
prompt_a
prompt_b
```

返回：

```text
compare_group_id
a.trace_id
b.trace_id
a.answer
b.answer
latency diff
output chars diff
```

可以这样讲：

```text
Prompt 改动很难只凭感觉判断好坏，所以我做了一个轻量 A/B Compare。它用同一个输入、同一个 provider 参数，分别调用 prompt A 和 prompt B，并把两条运行记录写入 run log，后续可以通过 compare_group_id 回放。
```

---

## 7. Run Log 和 Replay 怎么讲

运行记录写入：

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

Replay 接口：

```text
GET /runs/trace/{trace_id}
GET /runs/compare/{compare_group_id}
```

### 面试表述

我用 JSONL 做了一个最小可用的 run log，因为它 append-only、容易调试，也方便用 shell 或 Python 分析。对 LLM 应用来说，trace 和 replay 很重要，因为模型输出不稳定，prompt 实验如果不记录下来，后续很难复盘。

---

## 8. RAG Pipeline 怎么讲

### 8.1 入库流程

```text
POST /kb/documents
→ 校验 text/source/title
→ extract_index_text()
→ split_text()
→ embedding
→ upsert Chroma
→ 保存原文到 kb/docs/{doc_id}.md
→ 追加 metadata 到 kb/docs.jsonl
```

### 8.2 检索流程

```text
query
→ embedding
→ Chroma search
→ hits
```

Hit 包含：

```text
doc_id
chunk_id
score
text
source
title
```

### 8.3 Chat RAG 流程

```text
用户问题
→ candidate_k 召回
→ rerank_hits()
→ top_k 截断
→ build_rag_context()
→ 注入 system prompt
→ LLM answer
→ metadata.rag.citations
```

### 面试表述

我的 RAG 不是只做一个 `/kb/search`，而是完整接入了 `/chat` 和 `/chat/stream`。当 `use_kb=true` 时，系统会先从 KB 检索相关 chunks，然后把上下文注入给模型，并在响应里返回 citations。这样回答不只是生成文本，还能追溯证据来源。

---

## 9. 为什么需要 `candidate_k`

可以这样讲：

```text
最初我直接用 top_k 检索结果注入上下文，但发现有些问题的正确 chunk 在原始向量检索里不一定排在 top-3，有时排在更后面。于是我引入 KB_CANDIDATE_K=50，先召回较大的候选池，再用 query-aware rerank 选择最终 top_k。
```

它解决的问题：

```text
1. 向量检索 top-3 偶尔漏掉正确 chunk；
2. 工程类关键词问题需要结合标题、source、关键词判断；
3. top_k 是最终上下文数量，candidate_k 是重排候选池大小，两者职责不同。
```

---

## 10. RAGBackend 抽象怎么讲

v2 中我把 RAG 逻辑抽象成：

```text
RAGBackend.build_context(query, top_k) -> RAGContextResult
```

返回：

```text
context_text
citations
extra
```

支持：

```text
RAG_BACKEND=native
RAG_BACKEND=langchain
```

### 面试表述

Day25 之前，`routes_chat.py` 里直接处理 embedding、Chroma、Hit、rerank 和 context 拼接。这样同步和流式接口都会重复关心 RAG 细节。v2 中我把这部分抽成 `RAGBackend`，route 层只调用 `build_context()`，然后把结果转换成原有 response contract。

这样做的好处是：

```text
1. route 层变薄；
2. sync 和 stream 共用同一套 RAG 构建逻辑；
3. native 和 langchain 可以切换；
4. 外部 API contract 不变；
5. 后续可以继续接 Query Rewrite 或其他 retriever。
```

---

## 11. Native Backend 和 LangChain Backend 怎么讲

### 11.1 Native Backend

Native backend 封装手写 RAG：

```text
query
→ get_embedding_engine(settings)
→ Chroma query
→ Hit
→ rerank_hits()
→ build_rag_context()
→ RAGContextResult
```

讲法：

```text
Native backend 的优点是透明、可控、容易调试。它适合学习和面试讲解，因为每一步都是我自己写的。
```

### 11.2 LangChain Backend

LangChain backend 使用：

```text
langchain_chroma.Chroma
```

但仍然复用项目自己的 embedding engine：

```text
get_embedding_engine(settings)
→ ProjectEmbeddings
→ langchain_chroma.Chroma
```

讲法：

```text
我没有直接让 LangChain 使用另一个 embedding 模型，而是把项目已有的 embedding engine 包装成 LangChain Embeddings。这样可以保证文档入库和查询时使用同一个向量空间，避免 embedding mismatch。
```

### 11.3 为什么 LangChain 是可选依赖

```text
requirements.txt              # 基础服务和 CI
requirements-langchain.txt    # 可选 LangChain 依赖
```

讲法：

```text
LangChain 不是基础服务必须依赖，所以我把它放到 optional requirements 里。基础 CI 使用 mock embedding 和 mock provider，保持快速稳定。LangChain 相关测试用 importorskip 保护。
```

---

## 12. RAG Observability 怎么讲

Day27 增加了 RAG timing：

```text
backend
vectorstore
embedding_ms
retrieval_ms
rerank_ms
context_build_ms
total_ms
```

这些字段出现在：

```text
/chat metadata.rag
/chat/stream meta.rag
/chat/stream usage.rag
/chat/stream error.rag
```

### 面试表述

RAG 系统不只要回答对，还要知道慢在哪里。所以我把 RAG 各阶段耗时透传到 metadata 中。这样当我切换 native/langchain 或引入 Hybrid RAG 时，可以观察 retrieval_ms、rerank_ms、total_ms 是否变化，而不是凭感觉判断性能。

---

## 13. Hybrid RAG 怎么讲

Day28 将 rerank 升级为 Hybrid RAG：

```text
向量检索
→ 词面打分
→ 融合重排
→ top_k context
```

配置：

```text
retrieval_mode = hybrid
fusion = vector_lexical
vector_weight = 0.7
lexical_weight = 0.3
```

融合信号：

```text
1. vector score
2. lexical score
3. query-aware rule bonus
```

词面信号来自：

```text
query tokens
title
source
text
exact phrase
CJK n-grams
```

### 面试表述

纯向量检索对语义相似问题有效，但工程类问题经常包含非常关键的词面信号，比如 `docs.jsonl`、`candidate_k`、`SSE event block`、`DELETE /kb/documents/{doc_id}`。这些 token 一旦出现在 title、source 或 text 中，就应该影响排序。因此我引入轻量 lexical score，再和 vector score 做融合重排。

我没有直接上 Cross-Encoder reranker，因为当前项目有 p95 latency gate，重型 reranker 会增加依赖和延迟。Hybrid RAG 是一个更轻量、可控、容易调试的选择。

---

## 14. QA20 评测和 Regression Gates 怎么讲

### 14.1 评测集

项目有 20 条 RAG QA：

```text
eval/qa_rag_20.jsonl
```

评测脚本：

```text
scripts/eval_qa_rag.py
scripts/build_eval_report.py
```

### 14.2 指标

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

### 14.3 Strict gates

```text
answer_hit_rate >= 0.90
citation_hit_rate >= 0.95
effective_rag_rate >= 0.95
title_hit_rate >= 0.85
p95_latency_ms <= 6000
failed_count == 0
```

### 面试表述

我没有只看模型回答“感觉对不对”，而是做了一个小型 QA20 回归集。评测不只看答案关键词，也看 citations 是否命中、RAG 是否实际生效、title metadata 是否正确、p95 latency 是否超过门槛。这样每次改 RAG 逻辑都可以用 strict gate 做回归。

---

## 15. Day29 Eval Workflow 怎么讲

Day29 新增：

```text
scripts/seed_kb.py
scripts/run_rag_eval_workflow.py
```

完整流程：

```text
reset KB runtime
→ restart uvicorn
→ seed docs/kb_seed/01-11
→ provider warmup
→ QA20 eval
→ strict report
→ print summary
```

最终结果：

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

### 面试表述

Day28-C 暴露出一个真实工程问题：RAG 评测结果高度依赖 live KB 状态。如果 KB 里残留 demo 文档，或者 title/source metadata 不一致，citation gate 就会失败。所以 Day29 我把 seed 和 eval workflow 脚本化。`seed_kb.py` 固定 seed 文档范围、source、title 和 manifest；`run_rag_eval_workflow.py` 把 seed、eval、report 串起来。

第一次 workflow 实跑时，质量指标都通过，但 p95 latency 超过 6000。定位后发现是本地 Ollama 首次请求影响了 20 样本 p95，所以我加了 provider warmup，把 p95 从 6512ms 降到 2750ms，strict gate 通过。

---

## 16. 真实排障案例怎么讲

### 16.1 CI 顶层依赖问题

问题：

```text
CI 失败，因为 embeddings.py 顶层 import sentence_transformers。
mock embedding 的测试也被迫依赖重型 HF 包。
```

修复：

```text
把 sentence_transformers 改为 HF provider 内部懒加载。
EMBEDDING_PROVIDER=mock 时不需要安装 sentence-transformers/torch/transformers。
```

面试讲法：

```text
这个问题说明本地能跑不代表 CI 能跑。重依赖应该按 provider 懒加载，不能污染基础测试路径。
```

### 16.2 QA Seeds 污染检索

问题：

```text
KB seed 文档中的 Keywords / QA Seeds 被索引，导致检索命中评测提示本身。
```

修复：

```text
新增 extract_index_text()，遇到 ---、# Keywords、# QA Seeds、# Appendix、# Changelog 截断。
```

面试讲法：

```text
RAG 入库不应该把维护信息和答案提示一起索引，否则评测会虚高。
```

### 16.3 rerank 过拟合

问题：

```text
rerank 一度把很多问题都吸到 RAG in Chat/Stream 文档。
```

修复：

```text
取消无条件加分，改成 query 触发的 title/topic boost。
```

面试讲法：

```text
规则重排要避免全局偏置，应该只在 query 命中特定主题词时触发。
```

### 16.4 Day28 citation exact match 失败

问题：

```text
expected_sources = ["kb_seed"]
actual source = "docs/kb_seed/07_KB Ingest & Search.md"
exact match 导致 citation_hit_rate = 0。
```

修复：

```text
改成 normalized substring match，并支持 title/source fallback。
```

面试讲法：

```text
评测口径要和运行时 metadata 形状一致，否则会出现系统实际引用正确但评测判错。
```

### 16.5 Day29 p95 latency 失败

问题：

```text
质量指标全部通过，但 p95_latency_ms = 6512，超过 6000。
```

修复：

```text
正式 eval 前增加 provider warmup。
```

效果：

```text
p95_latency_ms: 6512 → 2750
```

面试讲法：

```text
小样本 latency gate 对冷启动非常敏感。本地 Ollama 首次请求会污染 p95，所以我用 warmup 让评测更稳定，但没有放宽 gate。
```

---

## 17. 设计取舍怎么讲

### 17.1 为什么保留 Native RAG

```text
Native RAG 透明、可控、容易调试，适合学习和讲解。
```

### 17.2 为什么接 LangChain

```text
LangChain 是生态集成入口，但不应该让项目被框架绑死。
所以我把它做成可选 backend，而不是替换整个 RAG 主链路。
```

### 17.3 为什么不用 Cross-Encoder

```text
Cross-Encoder 可能提升质量，但会增加延迟和依赖复杂度。
当前项目有 p95 latency gate，所以先做轻量 Hybrid RAG。
```

### 17.4 为什么 Ollama QA20 不进 CI

```text
Ollama QA20 依赖本地模型、网络和硬件。
CI 应该保持 deterministic，所以 CI 跑 mock tests，本地 acceptance 跑 Ollama workflow。
```

---

## 18. 项目边界怎么讲

当前边界：

```text
1. 没有认证和鉴权；
2. 没有数据库级文档元数据；
3. 没有多租户隔离；
4. 没有生产级日志系统；
5. 没有后台任务队列；
6. 没有真实 token accounting；
7. 没有 query rewrite；
8. 没有 Cross-Encoder reranker；
9. 没有在线评测 dashboard；
10. 还没有云端部署加固。
```

可以这样讲：

```text
这个项目目前定位是 LLM 应用工程训练项目，不是生产 RAG 平台。所以我优先做了 API contract、RAG、评测、CI、可观测性这些基础工程能力。后续如果继续推进，我会补 Docker Compose、云端部署、数据库元数据、后台任务队列、用户级 KB、query rewrite 和 Agent 层。
```

---

## 19. 面试官常问问题与回答

### Q1：你这个项目和简单调用大模型 API 有什么区别？

答：

```text
简单调用 API 只解决“能生成回答”。这个项目更关注工程闭环：provider 抽象、同步/流式接口契约、PromptHub、A/B Compare、run replay、KB/RAG、citations、评测回归、CI、可观测性和可复现 workflow。也就是说，它不是一次性 demo，而是一个可维护的 LLM 应用后端。
```

### Q2：RAG 具体怎么实现？

答：

```text
入库时先清洗 index text，再滑窗分块，计算 embedding，写入 Chroma，同时保存原文和 docs.jsonl 元数据。问答时，如果 use_kb=true，会取最新用户问题作为 query，先用 candidate_k 召回较大候选池，再 rerank，截断到 top_k，构造 context 注入给模型，最后在 metadata.rag 中返回 citations。
```

### Q3：为什么需要 Hybrid RAG？

答：

```text
纯向量检索对语义相似问题有效，但工程项目问题经常有强词面信号，比如 docs.jsonl、candidate_k、SSE、DELETE /kb/documents。Hybrid RAG 会把 vector score 和 lexical score 融合，再叠加 query-aware rule bonus，从而提升这类问题的召回和排序稳定性。
```

### Q4：LangChain 在项目里起什么作用？

答：

```text
LangChain 是可选 RAG backend，不是整个系统的核心依赖。项目默认 native backend，LangChain backend 使用 langchain_chroma.Chroma，但复用项目自己的 embedding engine，避免 embedding space mismatch。这样既能接生态，又能保持项目可控。
```

### Q5：怎么证明 RAG 效果没有退化？

答：

```text
我做了 QA20 评测集和 strict regression gates。指标包括 answer_hit_rate、citation_hit_rate、effective_rag_rate、title_hit_rate、p95_latency_ms 和 failed_count。每次改 RAG 逻辑后，可以跑 eval workflow 生成 strict report。Day29 最终结果是 answer 90%、citation 100%、effective RAG 100%、title 95%、p95 2750ms，strict gate 通过。
```

### Q6：遇到过最有价值的问题是什么？

答：

```text
Day28-C 很典型。第一次评测失败不是 Hybrid RAG 代码问题，而是 live KB 里残留 demo 文档。重建 KB 后 citation 仍是 0，进一步发现是评测脚本用 exact match，而 expected_sources 是 kb_seed，实际 source 是 docs/kb_seed/xxx.md。最后我修了 citation matching，并把 seed 流程脚本化。这个问题让我意识到 RAG 评测不仅是模型质量问题，还包括 KB 状态、metadata 和评测口径一致性。
```

### Q7：为什么 CI 不跑 Ollama QA20？

答：

```text
因为 Ollama QA20 依赖本地模型服务、Windows/WSL 网络、硬件性能和 runtime KB 状态。它不适合放进 CI。CI 应该跑快速确定性的 mock tests；真实模型评测作为本地 acceptance workflow。
```

---

## 20. 2 分钟压缩讲稿

如果面试官只给 2 分钟，可以这样说：

```text
我做了一个叫 chat-api 的 LLM 应用工程项目，底层是 FastAPI，支持同步 /chat 和 SSE /chat/stream，模型 provider 支持 mock 和本地 Ollama。项目不是只调模型，而是做了一整套 LLM 应用工程闭环：PromptHub、Prompt A/B Compare、run log、trace replay、KB 入库检索、RAG 问答、citations、QA20 评测、strict regression gates 和 CI。

RAG 部分是重点。最初我实现了文档入库、清洗、分块、embedding、Chroma 检索和上下文注入。v2 阶段我把 RAG 从 route 层抽象成 RAGBackend，支持 native 和 LangChain 两种后端，而且同步和流式接口共用同一套 RAG 构建逻辑。之后我增加了 RAG observability，可以看到 embedding、retrieval、rerank、context build 的耗时。Day28 又把 rerank 升级成 Hybrid RAG，用 vector score 加 lexical score 加 query-aware bonus 融合排序。

最后我做了可复现评测 workflow。Day28 时我发现 QA20 结果会受 live KB 状态和 citation metadata 影响，所以 Day29 新增 seed_kb.py 和 run_rag_eval_workflow.py，把 reset、seed、provider warmup、eval 和 strict report 串起来。最终 QA20 strict gate 通过：answer 90%、citation 100%、effective RAG 100%、title 95%、p95 latency 2750ms。
```

---

## 21. 5 分钟标准讲稿

如果面试官愿意听完整项目，可以这样讲：

```text
这个项目是我为了训练 LLM 应用工程能力做的。最开始是 FastAPI 的 /health 和 /chat，后来逐步扩展成一个具备同步聊天、SSE 流式输出、PromptHub、Prompt Compare、Run Replay、KB、RAG、评测回归和 CI 的完整项目。

基础层面，我实现了 provider 抽象，支持 mock 和 ollama。mock 用于测试，ollama 用于本地真实模型。/chat 是同步接口，返回 answer 和结构化 metadata；/chat/stream 是 SSE 流式接口，定义了 meta、token、usage、done、error 事件。同步接口下游失败返回 HTTP 502，流式接口因为连接已经建立，所以通过 event:error 返回业务错误。

Prompt 层面，我做了 PromptHub，通过 prompt_id 和 prompt_version 管理模板。又做了 A/B Compare，同一个输入可以跑两套 prompt，比较 latency 和输出长度，并通过 compare_group_id 写入 run log。后续可以用 trace_id 或 compare_group_id 回放。

RAG 是项目主线。入库时会对文档做 index text cleaning，避免 Keywords 和 QA Seeds 污染向量库，然后滑窗分块、embedding、写入 Chroma，同时保存 docs.jsonl 和原始文档。问答时，如果 use_kb=true，会先用 candidate_k 召回更大的候选池，再 rerank，截断到 top_k，构造 context 注入给模型，并返回 citations。

v2 阶段我把 RAG 做了架构升级。原来 RAG 细节在 routes_chat.py 里，后来我抽象成 RAGBackend，支持 native 和 langchain。native 是我手写的透明实现；langchain backend 使用 langchain_chroma，但复用项目自己的 embedding engine，避免文档和查询 embedding 空间不一致。同时我增加了 RAG observability，把 embedding_ms、retrieval_ms、rerank_ms、context_build_ms、total_ms 暴露到 metadata.rag。

Day28 我做了 Hybrid RAG。因为工程类问题经常有强词面信号，比如 docs.jsonl、candidate_k、SSE、DELETE /kb/documents，纯向量检索不一定稳定。所以我把 vector score、lexical score 和 query-aware rule bonus 融合排序，并把 retrieval_mode、fusion、vector_weight、lexical_weight 暴露到 metadata。

评测方面，我做了 QA20 和 strict regression gates，不只看答案关键词，还看 citation、RAG 是否生效、title metadata 和 p95 latency。Day29 我进一步把评测流程脚本化，新增 seed_kb.py 和 run_rag_eval_workflow.py，把 reset、seed、warmup、eval、report 串起来。最终本地 Ollama QA20 strict gate 通过，answer 90%、citation 100%、effective RAG 100%、title 95%、p95 2750ms。
```

---

## 22. 简历项目描述可提炼版本

### 22.1 一句话

```text
基于 FastAPI 构建本地 LLM Chat API，支持同步/流式聊天、PromptHub、A/B Compare、Run Replay、RAG、Hybrid Retrieval、评测回归与 CI。
```

### 22.2 三条 bullet

```text
- 设计并实现 FastAPI LLM Chat Service，支持 mock/ollama provider、同步 /chat、SSE /chat/stream、结构化错误处理、trace_id 与 latency metadata。
- 构建 RAG 知识库闭环，支持文档入库、文本清洗、滑窗分块、Chroma 检索、candidate_k 召回、Hybrid RAG fusion rerank、citations 溯源，并通过 RAGBackend 抽象支持 native/langchain 后端切换。
- 搭建 QA20 RAG 评测与回归体系，指标覆盖 answer/citation/effective_rag/title/p95 latency，新增 seed/eval workflow 自动完成 KB reset、seed、provider warmup、eval 与 strict report，最终 citation_hit_rate=100%、effective_rag_rate=100%。
```

### 22.3 偏工程版本

```text
- 将 RAG 逻辑从 API route 层解耦为 RAGBackend 抽象，统一 /chat 与 /chat/stream 的上下文构建流程，支持 native 与 LangChain Chroma backend，并通过 contract tests 保证 API 输出兼容。
- 为 RAG pipeline 增加 observability，透传 embedding/retrieval/rerank/context_build/total latency，辅助定位 Hybrid RAG 引入后的性能变化。
- 修复 CI 重依赖顶层导入、QA Seeds 索引污染、citation exact-match 误判、Ollama 冷启动污染 p95 latency 等工程问题，提升项目可维护性与评测稳定性。
```

---

## 23. Day30-C 收口建议

生成本文档后，建议执行：

```bash
pytest -q

git status
git add docs/interview_talk_track.md
git commit -m "docs(day30): add interview talk track"
git push
```

等 CI 绿后，Day30-D 再更新：

```text
README.md
HANDOFF.md
```

并把 v2 收口状态写清楚。
