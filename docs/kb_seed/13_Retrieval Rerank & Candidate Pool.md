# Header

* Title：13_Retrieval Rerank & Candidate Pool（candidate_k + query-aware rerank + top_k）
* Source：kb_seed
* Scope：

  * candidate_k 与 top_k 的区别
  * query-aware rerank
  * 强锚点词加权
  * title boost
  * rerank 过拟合风险
  * q019 召回问题复盘
* Out of scope：

  * RAG Eval Report 与 regression gates（见 12）
  * KB 入库与 Chroma upsert（见 07）
  * Chat/Stream RAG 注入协议（见 08）
* Files：

  * `src/app/kb/rag_context.py`
  * `src/app/api/routes_chat.py`
  * `src/app/core/settings.py`
  * `eval/qa_rag_20.jsonl`
  * `tests/kb/test_rag_rerank.py`
* Related Tests：

  * `tests/kb/test_rag_rerank.py`

# TL;DR

* `candidate_k` 是候选池大小，用于先从向量库多召回一些 chunks。
* `top_k` 是最终注入给模型的 chunks 数量，用于控制上下文预算。
* rerank 发生在 candidate hits 和 top_k 截断之间。
* query-aware rerank 只在 query 命中特定主题词时才给对应文档或 chunk 加分。
* 不能无条件给 `RAG in Chat/Stream` 加分，否则所有问题都会被 RAG 文档吸走。
* Day19 最终采用 `candidate_k=50 + query-aware rerank`，让术语型问题稳定召回正确 chunk，同时避免全局偏置。

# Why Candidate Pool

纯向量检索的 top_k 有时会漏掉关键 chunk。

例如 q019 问：

```text
candidate_k 在 RAG 中用来做什么？为什么 top_k 可以小但 candidate_k 可以更大？
```

原始向量检索中，真正包含 `candidate_k / rerank / top_k` 的 chunk 曾经排在 rank20。
如果只取 top_k=3 或 top_k=5，正确 chunk 根本进不了上下文，模型只能回答“不确定/需要更多上下文”。

因此需要两阶段策略：

```text
Chroma search(candidate_k)
→ query-aware rerank(candidate hits)
→ final top_k
→ build_rag_context
→ LLM generate
```

# candidate_k vs top_k

## candidate_k

`candidate_k` 表示候选池大小。

作用：

* 提高召回覆盖率。
* 给 rerank 提供更多候选。
* 降低关键 chunk 被早期截断的概率。

示例：

```text
candidate_k = 50
```

表示先从 Chroma 中取 50 个候选 chunks。

## top_k

`top_k` 表示最终注入给模型的 chunks 数量。

作用：

* 控制 prompt context 长度。
* 降低模型输入成本。
* 减少噪声上下文。
* 稳定 latency。

示例：

```text
top_k = 3
```

表示 rerank 后只取前 3 个 chunks 注入上下文。

## Why candidate_k can be larger than top_k

因为二者解决的问题不同：

* `candidate_k` 解决召回覆盖。
* `rerank` 解决候选排序。
* `top_k` 解决上下文预算。

所以 `candidate_k` 可以比 `top_k` 大很多。

# Query-aware Rerank

query-aware rerank 的核心原则：

```text
只有 query 触发了某个主题，才给对应文档或 chunk 加分。
```

不能写成：

```text
只要某个 chunk 属于 RAG in Chat/Stream，就永远加分。
```

否则所有问题都会偏向同一篇文档。

# Strong Terms

对于术语型问题，可以定义强锚点词。

示例：

* `candidate_k`
* `rerank`
* `top_k`
* `候选池`
* `重排`
* `精排`

规则：

* 如果 query 中出现强锚点词；
* 且 hit.text 中也出现该词；
* 则给该 hit 加分。

这能让术语型问题稳定命中真正解释该术语的 chunk。

# Topic Rules

除了强锚点词，还可以维护 topic-level title boost。

示例：

* query 含 `docs.jsonl` / `split_text` / `upsert_chunks` → boost `KB Ingest & Search`
* query 含 `/kb/documents` / `DELETE` / `tombstone` → boost `KB Documents Management`
* query 含 `tmp_path` / `monkeypatch` / `KB_DIR` → boost `Testing Strategy`
* query 含 `bce-embedding-base_v1` / `/mnt/c` / `WSL` → boost `Environment & Ops`
* query 含 `SSE` / `event:` / `data:` / `block` → boost `Stream SSE Protocol`
* query 含 `prompt_id` / `prompt_version` / `prompt_vars` → boost `PromptHub`
* query 含 `compare_group_id` / `A/B` → boost `A/B Compare`
* query 含 `runs.jsonl` / `/runs/trace` / `trace_id` → boost `Run Logs & Replay`
* query 含 `candidate_k` / `rerank` / `top_k` → boost `RAG in Chat/Stream`

这些规则是轻量、可解释的，不是黑盒模型。

# Day19 q019 Failure and Fix

## Failure 1：candidate_k chunk 入库但排太后

现象：

```text
candidate_k/rerank/top_k 正确 chunk 出现在 rank20。
top5 中没有正确 chunk。
```

原因：

* 纯向量检索对工程术语不够稳定。
* top_k 太小会提前截断正确 chunk。
* candidate_k=20 刚好卡边界，容易波动。

修复：

```text
KB_CANDIDATE_K = 50
```

让正确 chunk 有机会进入候选池。

## Failure 2：answer_hit 假阳性

现象：

模型回答：

```text
不确定/需要更多上下文，文档中没有 candidate_k 的说明。
```

但因为回答中包含 `candidate_k` 和 `top_k`，关键词命中，导致 answer_hit 被误判为 true。

修复：

* `score_answer` 增加 uncertain guard。
* 如果回答出现“不确定/需要更多上下文/文档中未提供”等模板，即使命中关键词，也不能算 answer_hit。

## Failure 3：rerank 过度偏向 RAG 文档

现象：

为了修 q019，曾经无条件给 `RAG in Chat/Stream` 加分。
结果 q002/q003/q005/q006 等问题全部被错误召回到 RAG 文档。

原因：

```text
title boost 没有 query-aware 条件。
```

修复：

```text
只有 query 中出现 candidate_k/rerank/top_k 等触发词时，才 boost RAG in Chat/Stream。
```

最终结果：

* q019 真通过。
* q002/q003/q006/q012 等 probe 题也回到正确文档。
* QA20 最终 answer_hit_rate 达到 95%。

# Rerank Flow

整体流程：

```text
query
→ vector search(candidate_k=50)
→ rerank_hits(query, hits)
→ hits[:top_k]
→ build_rag_context
→ citations
→ LLM answer
```

关键点：

* rerank 不改变原始 chunk 内容。
* rerank 只改变候选排序。
* top_k 截断在 rerank 之后发生。
* citations 来自最终注入 context 的 hits。
* metadata.rag.candidate_k 记录候选池大小，便于排障。

# Rerank Scoring

推荐分数组成：

```text
final_score = vector_score + query_term_bonus + topic_title_bonus
```

其中：

* `vector_score` 来自 Chroma。
* `query_term_bonus` 来自 query 与 chunk text 的强词重合。
* `topic_title_bonus` 来自 query 触发的文档主题加分。

注意：

* 不要让 bonus 完全取代 vector_score。
* 不要写全局 title boost。
* 不要对所有 query 都 boost 同一篇文档。
* bonus 应保持可解释、可调试。

# Observability

RAG metadata 应暴露：

* `rag.enabled`
* `rag.top_k`
* `rag.hits`
* `rag.candidate_k`
* `rag.context_chars`
* `rag.citations`
* `rag.error`

这些字段用于：

* 判断是否使用 RAG。
* 判断候选池大小。
* 判断最终注入数量。
* 判断召回文档是否正确。
* 定位 latency 或 hallucination 问题。

# Tests Mapping

`tests/kb/test_rag_rerank.py` 应覆盖：

1. query 包含 `candidate_k/rerank/top_k` 时，`RAG in Chat/Stream` 相关 chunk 被排前。
2. query 是 `docs.jsonl` 时，不应被 `RAG in Chat/Stream` 无条件吸走。
3. query-aware title boost 生效。
4. 无 hits 时返回空列表。
5. rerank 不丢失原始 hit 字段。

这些测试用于防止 q019 修复后再次引入全局偏置。

# Failure Modes

## RAG 文档吸走所有问题

表现：

* 大量不同主题问题的 citations 都是 `RAG in Chat/Stream`。
* answer_hit 大幅下降。
* title_hit 大幅下降。

原因：

* 无条件 title boost。
* strong terms 加分不看 query。
* topic_rules 太宽。

修复：

* 所有 boost 必须 query-aware。
* 增加 `tests/kb/test_rag_rerank.py`。
* 用 probe 5 验证多个主题分流是否正常。

## q019 找不到 candidate_k

表现：

* answer 说“不确定/需要更多上下文”。
* citations 不含 `RAG in Chat/Stream`。
* metadata.rag.candidate_k 太小。

原因：

* candidate_k 太小。
* 正确 chunk 在候选池外。
* rerank 未接入 `/chat` 主流程。

修复：

* 设置 `KB_CANDIDATE_K=50`。
* 确认 `routes_chat.py` 调用 `rerank_hits`。
* 确认 `/chat` 与 `/chat/stream` 都接入 rerank。

## answer_hit 被假阳性

表现：

* answer 说无法回答。
* 但因为包含 query 关键词，被算作 answer_hit=true。

修复：

* 增加 uncertain guard。
* 对 uncertain=true 的回答直接判 answer_hit=false。

# Pitfalls & Debug Playbook

## 检查 rerank 是否接入

```bash
grep -R "rerank_hits" -n src
```

期望看到：

```text
src/app/kb/rag_context.py:def rerank_hits(...)
src/app/api/routes_chat.py: hits = rerank_hits(...)
```

## 检查候选池大小

查看 `/chat` 返回：

```json
"rag": {
  "candidate_k": 50,
  "top_k": 3,
  "hits": 3
}
```

## 检查某题引用是否正确

```bash
cat eval/results/rag_eval_20.jsonl | python -m json.tool
```

或按 qid 过滤结果。

## 检查 query-aware 是否过拟合

准备 probe 题：

* q002：docs.jsonl
* q003：split_text
* q006：WSL / bce-embedding-base_v1
* q012：SSE block
* q019：candidate_k

如果这些题都命中不同的正确文档，说明 rerank 没有全局偏置。

---

# Keywords

candidate_k
top_k
rerank
query-aware rerank
candidate pool
retrieval
title boost
strong terms
RAG in Chat/Stream
vector score
regression test
q019

# QA Seeds

Q: candidate_k 和 top_k 的区别是什么？
A: candidate_k 是候选池大小，用于提高召回覆盖；top_k 是最终注入给模型的 chunk 数量，用于控制上下文预算。

Q: 为什么需要 rerank？
A: 纯向量检索可能把关键 chunk 排得很后，rerank 可以根据 query 强锚点和文档主题重新排序。

Q: 为什么不能无条件 boost RAG in Chat/Stream？
A: 因为无条件 boost 会让所有问题都偏向同一篇文档，导致其他主题召回失败。

Q: q019 的修复点是什么？
A: 将 candidate_k 提升到 50，并引入 query-aware rerank，让 candidate_k/rerank/top_k 问题稳定命中 RAG in Chat/Stream。
