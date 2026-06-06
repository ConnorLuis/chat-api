# Header
- Title: 08_RAG in Chat/Stream（Context Injection + Citations + Degrade）
- Source：kb_seed
- Scope：只讲RAG如何接入`/chat`与`/chat/stream`（注入、引用、降级、字段位置）
  - 不讲KB入库/检索实现细节
  - 不讲SSE协议格式
- Files：
  - chat：`src/app/api/routes_chat.py`
  - rag context builder：`src/app/kb/rag_context.py`
  - kb search client：`src/app/api/kb/routes_kb.py`
  - schemas：`src/app/llm/schemas.py` / `src/app/kb/schemas.py`
- Related Endpoints：
  - `POST /chat`
  - `POST /chat/stream`
  - `GET /kb/search`
- Related Tests：
  - tests/chat/test_chat_rag_contract.py
  - tests/stream/test_stream_rag_contract.py

# TL;DR
- RAG 开关由请求体 `use_kb` 与 `kb_top_k` 控制：开启后先 KB topK 检索，再把 chunks 注入 system context。
- 引用证据通过 `citations` 返回（doc_id/chunk_id/source/title），并在 `metadata.rag`（sync）与 meta/usage/error.rag（stream）里体现。
- KB 空/失败不阻塞主流程：降级为普通对话（hits=0、citations=[]），并用 `rag.error` 记录原因以便排障。
- `candidate_k` 是 RAG 检索的候选池大小，`top_k` 是最终注入给模型的 chunk 数量；`rerank` 负责在 candidate hits 中按强锚点词和标题重排后再截断到 top_k。
# RAG Goals
- Grounding：回答严格锚定检索证据，从根源降低大模型幻觉率
- Citations：引用可追溯、可纠错、可配合 Run 日志回放复盘
- Budget：严格管控上下文长度，通过 top_k / 截断 / 总长度做资源预算约束
- Degrade：知识库异常时自动降级，保障核心问答服务不中断
- Traceability：检索全链路可观测，命中、耗时、分块信息可查便于快速排障
- Reproducibility：检索参数与结果固化，支持 A/B 实验与效果可复现验证
- Maintainability：支持文档增量更新与分块重构，不影响线上服务可用性
# Request Contract
## 新增字段（/chat 与 /chat/stream 共用）
- `use_kb： bool` （默认false）
- `kb_top_k：int` （默认值 + 合法范围，建议1-20）
- （可选未来）`kb_filter` / `kb_ids`（先不做，写 out of scope）
## 触发条件
- `use_kb=True`且user query非空（最后一条 user message）
- 否则直接降级（不检索）
# Retrieval & Context Injection
## Retrieval（检索）
- query = “最后一条 user message 的 content”
- 调 `kb.search(kb_top_k)` 返回 hits
- 统计：
  - `hits = len(returned_hits)`
  - `context_chars = len(context_text)`（预算指标）
### Candidate Pool & Rerank（候选池与重排）

`candidate_k`、`rerank`、`top_k` 是 RAG 检索排序的三个核心参数：

- `candidate_k`：先从向量库召回更大的候选池，例如 20，用来提高召回覆盖率。
- `rerank`：对 candidate hits 做轻量重排，优先保留与 query 强锚点词匹配的 chunk。
- `top_k`：最终注入给模型的 chunk 数量，例如 3，用来控制上下文预算。

为什么 `candidate_k` 可以比 `top_k` 大：

- `candidate_k` 解决“先多召回，避免漏掉关键 chunk”。
- `rerank` 解决“候选里谁更应该排前面”。
- `top_k` 解决“最终上下文不能太长”。

因此，`candidate_k` 负责召回覆盖，`rerank` 负责精排，`top_k` 负责上下文注入预算。
## Context Injection（注入）
- 把检索结果拼成 context block，作为 system message 注入
- 顺序建议：
  - `[PromptHub system (可选)]`
  - `[RAG context system]`
  - `[原 messages...]`
## Context Block

- `### Context`
- `[1] (doc_id=..., chunk_id=..., source=..., title=...) <chunk_text>`
- `[2] ...`
并说明：
- citations 的编号与 context 中的 [1] [2] 对齐
# Citations Contract
## Citation 对象最小字段
- `doc_id`
- `chunk_id`
- `source`
- `title`（可为null）
## 返回位置
- `/chat`：`response.metadata.rag.citations`
- `/chat/stream`：
  - `meta.data.rag`：只摘要（enabled/top_k/hits/context_chars）
  - `usage.data.rag.citations`：完整 citations
  - `error.data.rag`：也带摘要 + error（可选带 citations_count）
- sync：metadata.rag = {enabled, top_k, hits, context_chars, citations: [...], error}
- stream：
  - meta.data.rag = {enabled, top_k, hits, context_chars}
  - usage.data.rag = {enabled, top_k, hits, context_chars, citations: [...], error}
# Budget & Truncation（上下文预算）
3 个预算规则：
- top_k 限制：kb_top_k 上限（建议 20）
- 每块截断：chunk_text 最多 N 字符（建议 300–800）
- 总长度上限：context 总字符数上限（建议 2k–6k）
目前与未来：
- 当前：只依赖 top_k，记录 context_chars
- 未来：加入 per-chunk truncate 与总 budget
# Degrade Strategy
## KB 空/无命中
- `rag.enabled=true`
- `rag.hits=0`
- `rag.citations=[]`
- `rag.error=null`
- 请求仍正常返回（/chat 200，/chat/stream 正常 meta→usage→done）
## KB 异常（可观测但不阻塞）
- `rag.error=str(e)` 写入
- `rag.hits=0`、`citations=[]`
仍返回结果（best-effort），但 run log/usage/error 里可看到 rag.error
# Observability & Evidence
- `trace_id`
- `metadata.latency_ms`
- `rag.hits/context_chars/citations/error`
- runs：记录 `rag_enabled/kb_top_k/rag_hits/context_chars/rag_error/citations_count`
# Tests Mapping
- `tests/chat/test_chat_rag_contract.py`
  - use_kb=true 时 metadata.rag 存在、citations 为 list
  - KB 空时 citations=[] 且仍 200
- `tests/stream/test_stream_rag_contract.py`
  - meta.rag 摘要存在
  - usage.rag.citations 存在
  - 空 KB 仍 meta/usage/done
# Pitfalls & Debug Playbook
- KB 未入库 → hits=0 citations=[]
- kb_top_k 过大 → latency 上升
- context 太长 → 模型回答变慢/漂移（记录 context_chars）
- citations 位置放错（meta 不应含 citations）
- KB 异常被吞掉但不记录 rag_error（排障困难）
- /chat vs /chat/stream 错误语义不同（502 vs event:error）
- 误把 score 当成概率（只是相似度排序）
- “回答末尾引用编号”与 citations 列表不一致（建议只把 citations 放 metadata）
---
# Keywords
use_kb, kb_top_k, context injection, citations, grounding, rag.hits, context_chars, rag.error, /chat, /chat/stream, meta.rag, usage.rag.citations, degrade
# QA Seeds
{"qid":"q001","question":"为什么 citations 放在 usage 而不是 meta？","expected_keywords":["citations","usage","meta","流式事件","时序","数据完备性","RAG","检索结果","事件顺序"],"min_hits":2,"expected_sources":["RAG in Chat/Stream"],"note":"考察SSE流式事件中meta与usage的职责分工，以及citations字段放置位置的契约设计逻辑"}
{"qid":"q002","question":"KB 空与 KB 异常的降级差异是什么？","expected_keywords":["KB空","KB异常","降级","hits","citations","rag.error","服务可用性","降级策略"],"min_hits":2,"expected_sources":["RAG in Chat/Stream"],"note":"考察RAG两种异常场景的降级规则、字段表现与服务保障策略差异"}
{"qid":"q003","question":"context_chars 有什么用？如何做预算控制？","expected_keywords":["context_chars","上下文预算","长度控制","top_k","截断","token预算","资源约束","RAG"],"min_hits":2,"expected_sources":["RAG in Chat/Stream"],"note":"考察RAG上下文长度统计字段作用，以及上下文预算的工程管控方法"}