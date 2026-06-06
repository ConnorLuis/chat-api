# Header
- Title：07_KB Ingest & Search（Docs Index + Chunking + Embedding + Chroma）
- Source：kb_seed
- Scope：只覆盖
  - `POST /kb/documents` 入库（save → chunk → embedding → upsert）
  - `GET /kb/search` 检索（query → embedding → topK hits）
  - docs.jsonl 的索引/状态语义（append-only）
- Out of scope：
  - `/kb/documents list/delete`（在 09）
  - `/chat RAG 注入`（在 08）
- Files：
  - 路由：`src/app/api/kb/routes_kb.py`
  - store：`src/app/kb/store.py`
  - chunking：`src/app/kb/chunking.py`
  - embeddings：`src/app/kb/embeddings.py`
  - chroma：`src/app/kb/chroma_store.py`
  - schemas：`src/app/kb/schemas.py`
- Related Tests：
  - `tests/kb/test_kb_ingest_contract.py`
  - `tests/kb/test_kb_search_contract.py`
# TL;DR
- KB 入库把文本/markdown 变成可检索的 chunks：save → chunk → embed → upsert。
- 检索把 query 向量化后在 Chroma 中 topK 返回 hits（text + score + metadata）。
- docs.jsonl 是 append-only 索引与状态日志，支持可审计与后续 list/delete 管理。
## Index Text Extraction（索引文本抽取）
- raw_text：原文，完整保存到 `docs/<doc_id>.md`，用于审计、查看与回放。
- index_text：用于 chunking / embedding / Chroma upsert 的索引文本。

`extract_index_text(raw_text)` 的作用是从原文中抽取“可索引正文”：
- 先统一换行符，兼容 Windows/WSL 的 CRLF。
- 遇到独立一行的 `---` 就截断，只保留其前面的正文。
- 如果没有 `---`，则遇到 `# Keywords`、`# QA Seeds`、`# Appendix`、`# Changelog` 等一级标题时截断。
- 这样可以避免 Keywords / QA Seeds / Appendix 等“评测或辅助内容”进入向量库，减少召回污染。
# Data Model（契约视角）
## IngestRequest
- `text / markdown`
- `title`(可选)
- `source`(可选，默认demo/test)
- `chunk_size`、`overlap`(可选)
- 返回：`doc_id` + `chunks_count` + metadata(trace_id/latency_ms)
## SearchRequest / SearchResponse
- 输入：`q`（非空）、`top_k`（默认/范围）
- 输出：`hits: [Hit] + metadata(trace_id/latency_ms)`
- Hit 的最小字段：
  - `doc_id`
  - `chunk_id`
  - `score`
  - `text`（可能截断）
  - `source`、`title`（可选）
  - `chunk_index`（int，可选但推荐）
## Chroma Upsert（upsert_chunks）
`upsert_chunks` 负责把分块文本、向量和元数据批量写入 Chroma collection。

核心输入包括：
- ids：通常使用 `chunk_id`，例如 `<doc_id>_chunk_<index>`。
- documents：chunk_text 列表。
- embeddings：每个 chunk 对应的向量。
- metadatas：每个 chunk 的结构化元数据。

metadata 至少应包含：
- `doc_id`：所属文档 id，用于删除、聚合和溯源。
- `chunk_id`：分块唯一 id，用于 citations 和回放。
- `chunk_index`：该 doc 内的 chunk 序号。
- `source`：文档来源。
- `title`：文档标题。
- `start/end`：chunk 在 index_text 中的位置。

`upsert` 的语义是“存在则更新，不存在则插入”，适合重复入库、重建索引或覆盖同一 chunk。
# docs.jsonl语义
为什么需要 docs.jsonl
- md 只是正文；jsonl 才是索引（title/source/created_at/deleted 等）
- 支持可审计、并发追加安全（append-only）
写入规则
- 每次入库追加一条“create 记录”
- 每次删除追加一条“tombstone 记录”
读取规则（为搜索/管理服务）
- 按 doc_id 聚合“最后状态”
- bad_lines（可选）：未来增强，统计 JSONL 坏行以提高鲁棒性
## save_document 落盘内容与索引字段

`save_document` 负责同时写入两类持久化数据：

- `docs/<doc_id>.md`：保存原始文档正文，用于审计、查看与回放。
- `docs.jsonl`：追加一条文档索引记录，用于 list/search/delete 等管理接口聚合文档状态。

一条 create 索引记录通常包含：

- `doc_id`：文档唯一标识。
- `title`：文档标题。
- `source`：文档来源，例如 `kb_seed` / `demo` / `test`。
- `created_at`：创建时间。
- `updated_at`：更新时间，create 时通常等于 created_at 或为空。
- `deleted`：删除状态，create 时为 false。
- `path`：可选，本地 md 文件路径。
- `chunks_count`：可选，文档切分出的 chunk 数量。

因此，md 文件保存正文，docs.jsonl 保存可管理、可审计、可聚合的元数据索引。
# Ingest Flow（入库流程）
- 生成 `doc_id`
- 保存 `docs/<doc_id>.md`
- 追加索引到 `docs.jsonl`（title/source/created_at）
- chunking：`split_text(text, chunk_size, overlap)` → chunks
- embedding：对每个 chunk 生成向量（mock / real）
- chroma upsert：ids=chunk_id，documents=chunk_text，metadatas={doc_id, chunk_index, source, title...} 
- chunk_index（int，表示该 doc 下第几个 chunk）
- 返回：doc_id + chunks_count +（可选）chunk_ids
- 可观测：trace_id/latency_ms（接口响应或日志）
## Chunking Details（split_text 滑窗分块）
`split_text(text, chunk_size, overlap)` 使用滑窗方式把长文本切成多个 chunk：

- `chunk_size`：每个 chunk 的最大字符长度。
- `overlap`：相邻 chunk 之间保留的重叠区域，用来减少语义被边界截断。
- `start/end`：记录每个 chunk 在原文中的起止位置，便于排查和溯源。
- `chunk_index`：表示该 doc 下第几个 chunk。
- `next_start`：下一轮窗口起点，通常由 `end - overlap` 推进。

为了防止滑窗死循环，需要保证：
- `overlap < chunk_size`
- `next_start` 必须大于当前 `start`
- 如果 `next_start <= start`，应强制推进或停止
- 当 `end >= len(text)` 时结束切分

因此，`chunk_size` 决定块大小，`overlap` 决定上下文连续性，`next_start` 决定滑窗能否稳定向前推进。
# Search Flow
- 校验 q.strip() 非空（空则 400）
- query embedding
- chroma query topK
- 组装 hits（score + text + metadata）
- 返回 hits + metadata(trace_id/latency_ms)
- 降级/失败：Chroma 不可用时返回什么（500/降级空结果，写清策略）
## Embedding Engines
KB 支持 mock / real 两类 embedding engine。

### MockEmbeddingEngine
`MockEmbeddingEngine` 主要用于本地测试和契约测试：
- deterministic：同一输入总是得到同一向量，结果可复现。
- hash-based：用文本 hash 构造固定维度向量。
- fixed dimension：维度固定，避免测试中维度不一致。
- L2 normalize：把向量归一化，便于 cosine 相似度计算。
- 不依赖外部模型，适合 CI / 单元测试 / 快速回归。

### HFEmbeddingEngine
真实 embedding engine 用于更接近生产的语义检索：
- 加载本地或远程 sentence-transformers 模型。
- encode 时可使用 `normalize_embeddings=True`。
- 与 Chroma cosine space 配合时，score 更可解释。
# Score / Similarity
KB 检索底层使用 Chroma 的 `collection.query(..., include=["distances"])` 返回距离（distance）。距离的语义是：distance 越小，越相似。
为了让上层更直观，我们把 distance 转成“相似度分数” `score`（score 越大越相似），并按 `score` 进行降序排序后返回 hits。
## 向量空间（hnsw:space）
创建 collection 时会设置 `metadata={"hnsw:space": space}`，默认使用 `cosine`。 
## distance → score 的转换
- cosine：`score = 1 - distance`
- l2：`score = 1 / (1 + distance)`（把距离压到 (0,1] 区间）
- ip：当前同样按 `score = 1 - distance` 处理（如果未来切换空间，需要再确认 Chroma 的 distance 定义）
- `hits.score` 为“越大越相似”的相似度分数（已转换），非原始 distance。
最终 `score` 会做 `round(score, 4)` 并返回。 
## 为什么 cosine 下 score 可用（embedding 归一化）

为了让 cosine 语义稳定，embedding 端会做 L2 归一化：
- `MockEmbeddingEngine` 会把 hash 向量做 L2 normalize 变成单位向量。
- `HFEmbeddingEngine` encode 时使用 `normalize_embeddings=True`。

因此在默认 `cosine` 空间下，`score≈1-distance` 是一个可解释、可比较的相似度指标（同一 collection 内比较）。

## 注意事项
- `score` 是用于排序的相对指标，只保证在同一向量空间/同一 embedding 策略下可比较。
- 如果更换 `hnsw:space` 或 embedding 模型，需要重新理解 distance 的含义与 score 的映射策略。
# Failure Modes
- q 为空/全空白 → 400
- Chroma 初始化失败/目录权限 → 500
- embedding 失败 → 500
- chunking 参数不合法（chunk_size 太小/overlap >= chunk_size）→ 400 推荐校验/未来增强
# Tests Mapping
test_kb_ingest_contract.py （doc_id、chunks_count、落盘/可检索）
test_kb_search_contract.py （hits 结构、空 query 400）
# Pitfalls & Debug Playbook
- chunk_size/overlap 选错导致 hits 很碎/很少
- mock embedding 维度不一致导致 chroma 报错
- docs.jsonl 与 chroma 不一致（文件存在但向量没写入）
- Windows/WSL 路径导致 KB_DIR 不一致
- top_k 太大导致 latency 上升
- 重新 seed 入库导致重复 doc（如何处理：新 doc_id / 去重策略）
---
# Keywords
docs.jsonl, doc_id, chunk_id, chunk_size, overlap, split_text, embedding, chroma, upsert, query, top_k, hits, score, source, title
# QA Seeds
{"qid": "q001", "question": "docs.jsonl 的作用是什么？为什么不只存 doc_id.md？", "expected_keywords": ["docs.jsonl", "元数据", "doc_id.md", "索引构建", "tombstone", "软删除", "追加写入", "审计溯源", "并发安全"], "min_hits": 2, "expected_sources": ["07_KB Ingest & Search"], "note": "考察文档元数据文件的核心作用，以及与原生MD文件拆分存储的设计考量"}
{"qid": "q002", "question": "chunk_size/overlap 如何影响检索命中？", "expected_keywords": ["chunk_size", "overlap", "文本分块", "重叠区间", "上下文完整性", "语义截断", "召回率", "检索精度", "碎片内容"], "min_hits": 2, "expected_sources": ["07_KB Ingest & Search"], "note": "考察分块大小、块重叠两个参数对知识库检索召回效果的影响逻辑"}
{"qid": "q003", "question": "upsert_chunks 为什么要带 doc_id/chunk_id 元数据？", "expected_keywords": ["upsert_chunks", "doc_id", "chunk_id", "元数据", "唯一标识", "数据更新", "去重", "溯源关联", "分块管理"], "min_hits": 2, "expected_sources": ["07_KB Ingest & Search"], "note": "考察分块批量写入接口携带文档/分块唯一ID元数据的设计目的与业务价值"}
# Minimal SearchResponse shape (example)
- metadata: { trace_id, latency_ms }
- hits: [...]（长度 ≤ top_k）
- hits[i].doc_id: <doc_id>
- hits[i].chunk_id: <doc_id>_chunk_<n>
- hits[i].chunk_index: <int>（该 doc 内第 n 个 chunk）
- hits[i].score: <float>（越大越相似；由 distance 转换而来）
- hits[i].text: <string>（chunk 内容，可能截断）
- hits[i].source: <string | null>
- hits[i].title: <string | null>