# Header
- Title：09_KB Documents Management（List/Delete + Tombstone + Chroma Cleanup）
- Source：kb_seed
- Scope：只覆盖
  - `GET /kb/documents`（列表/分页/include_deleted）
  - `DELETE /kb/documents/{doc_id}`（删除向量+删除文件+写 tombstone）
  - tombstone / append-only 索引语义（与 07 呼应，但这里讲“删除状态”）
- Out of scope：
  - ingest/search（在 07）
  - RAG 注入（在 08）
- Files（3–6 行）
  - 路由：`src/app/api/kb/routes_kb.py`
  - store 索引：`src/app/kb/store.py`（或你当前 store 文件）
  - chroma：`src/app/kb/chroma_store.py`
  - schemas：`src/app/kb/schemas.py`
- Related Tests：
  - `tests/kb/test_kb_documents_list_delete_contract.py`

# TL;DR
- docs.jsonl 是 append-only 的索引日志，list/delete 都以它为“事实来源”聚合出文档状态。
- 删除不是“改写历史”，而是追加 tombstone：同时清理 Chroma 向量与本地 md 文件。
- 管理接口对外返回 trace_id/latency_ms，并在 include_deleted 下可审计被删记录。
# Why Documents Management（现实工程价值）
- 可管理：清晰掌握知识库文档全貌，明确 KB 存量、类型与状态
- 可审计：通过 tombstone 记录删除时间、原因，实现全生命周期操作留痕
- 可纠错：误删 / 错删可完整追溯，支撑后续数据恢复与问题修正
- 提质量：清理过期 / 错误知识，阻断无效命中，从源头保障 RAG 效果稳定
- 可迭代：支持文档增量更新与平滑替换，不影响线上 RAG 服务可用性
- 可溯源：文档 - 分块 - 检索日志全链路关联，快速定位低质回答根源
- 控成本：清理冗余废弃文档，降低向量库存储与检索计算资源开销
- 守合规：敏感 / 过期文档及时下线，规避知识泄露与合规性风险
# Data Model
## DocumentItem（list 返回项最小字段）
- `doc_id`
- `title`（可为 null）
- `source`（可为 null）
- `created_at`（或你实际字段）
- `deleted`（bool）
- `deleted_at`（可为 null）
- `delete_reason`（可为 null）
## DocumentsListResponse
- `items: [DocumentItem]`
- `total: int`
- `limit: int`
- `offset: int`
- `metadata: {trace_id, latency_ms}`
## DeleteDocumentResponse
- `doc_id`
- `deleted: true`
- `metadata` 必含：
  - `trace_id, latency_ms`
  - `deleted_vectors（int）`
  - `deleted_file（bool）`
  - `marked_deleted`（bool，表示 tombstone 已写）
# docs.jsonl Tombstone Semantics
## 为什么不用“就地修改”
- append-only 更安全（并发/审计/回放）
- 历史可追溯（谁删的/为什么删）
## tombstone 记录长什么样（字段形状）
- type: {"type":"delete", "doc_id":..., "deleted_at":..., "reason":...}
- doc_id
- deleted_at
- reason
## list 聚合规则（“最后状态”）
- 读取 docs.jsonl
- 按 doc_id 聚合最新状态
- include_deleted=false 过滤掉 deleted=true
- 按 created_at desc（最新在前）
# GET /kb/documents（List Contract）
## Query 参数
- limit：默认 50，范围 1–200
- offset：默认 0
- include_deleted：默认 false
## 返回行为
- total 是过滤后
  - 推荐：total = 过滤后（include_deleted 应用后）且分页前的总数
- items 顺序：推荐按 created_at desc（最新在前）, 过滤后再按 offset/limit 分页
## Failure Modes
- docs.jsonl 不存在 → 返回空列表（200）
  - 推荐：空列表（更工程化）
# DELETE /kb/documents/{doc_id}（Delete Contract）
## 目标
- 删除=“使其不再被检索命中” + “状态可审计”。
## 删除步骤
- 根据 doc_id 在 Chroma 执行 delete（where doc_id）
- 删除本地文件 docs/<doc_id>.md
- 追加 tombstone 到 docs.jsonl 的 delete 记录至少包含：doc_id, deleted_at, reason（其余字段为实现细节）。
- 返回 DeleteDocumentResponse
- 可观测：trace_id/latency_ms
- 再次检索（可选说明）：不应再命中该 doc（理想效果）
## 删除 reason
- query 参数或 body
- 默认 reason："user_request" 或 null
## Failure Modes
- doc_id 不存在：
  - 返回 404
  - 幂等删除（200 + deleted_vectors=0 + marked_deleted=false）
- chroma delete 失败：返回 500 还是继续 tombstone？
- 文件删除失败：仍继续 tombstone
# Consistency（docs.jsonl 与 Chroma/文件的一致性）
- 现实中三个存储层（docs.jsonl、Chroma 向量、docs/<doc_id>.md 文件）可能出现短暂或长期不一致：
  - A：tombstone 已写入，但 Chroma delete 失败 → search 仍可能命中。
  - B：Chroma 已删除，但 tombstone 未写入 → list 仍显示未删（审计层不一致）。
  - C：文件已删除，但向量仍在 → search 仍命中（内容无法再溯源）。
- 当前策略：
  - 审计事实来源以 docs.jsonl 为准（是否删除、何时删除、原因）。
  - 检索事实来源以 Chroma 向量是否删除为准（是否还能被召回）。
  - 删除接口尽量做到“最终一致”：即使某一步失败，也要把失败原因记录到日志/返回统计里，便于排障与补偿。
- 未来增强（reconcile）：后台按 docs.jsonl 扫描聚合 doc 状态，对“应删未删”的向量/文件做补偿清理；对“向量删了但未 tombstone”的记录补写 tombstone（或标记异常）。
# Tests Mapping（锁死契约）
- test_kb_documents_list_delete_contract.py：
  - list 返回结构 + metadata(trace_id)
  - delete 返回结构 + metadata(trace_id) + marked_deleted
  - include_deleted=true 能看到 deleted=true 记录
# Pitfalls & Debug Playbook
- 忘记写 tombstone → list 看不到删除
- 删除了文件但没删向量 → search 仍命中
- include_deleted 默认 false 导致“以为删失败”
- limit/offset 边界（limit=0、offset<0）
- docs.jsonl 被手动改坏 → list 解析失败（未来 bad_lines）
- WSL/Windows 路径不统一导致 KB_DIR 位置错乱
- 删除后立即 search 仍命中（缓存/异步）— 如果你没有缓存就写“无缓存，理论上应立即生效”
- reason 为空导致审计信息缺失
---
# Keywords
/kb/documents, include_deleted, limit, offset, tombstone, deleted_at, delete_reason, docs.jsonl, chroma delete, where doc_id, consistency, audit, trace_id, latency_ms
# QA Seeds
{"qid":"q001","question":"为什么 tombstone 要 append-only，而不是就地修改？","expected_keywords":["tombstone","append-only","就地修改","不可篡改","审计溯源","并发安全","数据恢复","历史留存"],"min_hits":2,"expected_sources":["KB Documents Management"],"note":"考察知识库软删除标记的存储设计原则，以及append-only的工程核心价值"}
{"qid":"q002","question":"delete 要同时删哪些东西（向量/文件/索引）？哪个决定检索是否命中？","expected_keywords":["delete","向量库","文件","索引","doc_id","chunk_id","tombstone","检索命中"],"min_hits":2,"expected_sources":["KB Documents Management"],"note":"考察知识库删除操作的全链路清理范围，以及控制检索是否命中的核心依据"}
{"qid":"q003","question":"include_deleted 的意义是什么？total 应该怎么算？","expected_keywords":["include_deleted","已删除文档","查询过滤","total统计","有效文档","tombstone","分页计数"],"min_hits":2,"expected_sources":["KB Documents Management"],"note":"考察知识库查询参数作用，以及包含/排除已删除文档时的总数计算规则"}