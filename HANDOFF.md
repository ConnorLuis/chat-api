开始新对话前：**“继续 chat-api v2，从 Day27 开始（RAG Observability：latency breakdown + trace 增强），当前 Day26 已完成 LangChain RAG backend retriever，native/langchain 双 backend 均可通过契约测试。”**

# HANDOFF（给新对话用，更新至 Day24）

## 0. 环境与项目

- 环境：WSL2 Ubuntu + conda env=`chatapi` (Python 3.10)
- 项目：`~/projects/chat-api`（GitHub: ConnorLuis/chat-api）
- 当前 v2 分支：`v2-langchain-rag`
- v1 稳定分支：`master`
- Ollama：安装在 Windows；模型 `qwen2.5:7b` 已 pull
- WSL 访问 Windows Ollama：

```bash
WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"
```

如果做 Error Demo 时临时改成 `http://127.0.0.1:1`，演示结束后要恢复上面的 Windows 网关地址并重启 uvicorn。

---

## 1. 关键环境变量

LLM：

- `OLLAMA_BASE_URL`（默认 `http://127.0.0.1:11434`）
- `OLLAMA_MODEL`（默认 `qwen2.5:7b`）
- `OLLAMA_TIMEOUT_S`（默认 `60`）

运行日志：

- `RUN_LOG_PATH`（默认 `runs/prompt_runs.jsonl`）

KB / RAG：

- `KB_DIR`（默认 `kb`）
- `KB_CHROMA_DIR`（默认 `${KB_DIR}/chroma`）
- `KB_COLLECTION`（默认 `kb_chunks`）
- `KB_CHUNK_SIZE`（默认 `800`）
- `KB_CHUNK_OVERLAP`（默认 `120`）
- `KB_TOP_K`（默认 `5`）
- `KB_CANDIDATE_K`（默认 `50`，Day19 调整，用于先召回更大候选池再 rerank）
- `KB_MAX_CONTEXT_CHARS`（用于限制 RAG 注入上下文长度）
- `RAG_BACKEND`（默认 `native`；Day24 新增，支持 `native|langchain`）

Embedding：

- `EMBEDDING_PROVIDER`（默认 `mock`，可选 `mock|hf`）
- `EMBEDDING_MODEL`（HF embedding 模型路径/名称）
- `EMBEDDING_DIM`（mock embedding 维度）

---

## 2. 已完成进度概览（Day1–Day26）

### Day1–Day12：FastAPI Chat Service 基础能力

- Day1：`GET /health` OK。
- Day2：`POST /chat`（mock + schemas）、全局中间件（`x-trace-id` + latency log）、`POST /chat/stream`（mock streaming）OK。
- Day3：可插拔引擎 `LLMEngine`（mock/ollama）；`ChatRequest` 增加 `provider=mock|ollama`。
- Day4：补齐 `README.md`；新增 pytest（`/health`、`/chat mock`）；修复测试导入路径（`tests/conftest.py`）。
- Day5：`/chat/stream` 升级为 SSE（`text/event-stream`），事件：`meta/token/done/error`。
- Day6：SSE 标准化增强：`sse_event`（data 字符串化/JSON 序列化/多行）、新增 `event: usage`、结构化 `event: error`。
- Day7：同步接口对齐：`settings.py`（env 读取）；`ChatResponse.metadata`（provider/model/latency_ms）；契约测试 `test_chat_contract.py`。
- Day8：错误与日志工程化：`build_error()` 统一 502 detail 与 stream error；meta 增加 model；model 兜底为 `unknown`。
- Day9：README 增补；新增 SSE/stream 契约测试（事件块 `\n\n`、顺序 meta→token*→usage→done）。
- Day10：OpenAPI `/docs` 增强：schemas examples + 路由 summary/description/responses。
- Day11：新增 `/demo` 流式聊天演示页（fetch POST + ReadableStream 解析 SSE）。
- Day12：Demo 增强 Stop/Abort（AbortController）；AbortError 不视为业务错误。

### Day13–Day18：PromptHub、A/B Compare、RAG 最小闭环

- Day13：PromptHub 最小闭环：prompt_id/version + run log + demo 增强。
- Day14：Prompt A/B Compare：`POST /prompt/compare` + run log compare_group_id + demo compare 模式 + replay 工具 + 契约测试。
- Day15：PromptHub Query APIs：
  - `GET /prompts`
  - `GET /runs/trace/{trace_id}`
  - `GET /runs/compare/{compare_group_id}`
- Day16：RAG KB 最小闭环（Chroma）：
  - `POST /kb/documents`
  - `GET /kb/search`
  - 契约测试：`test_kb_ingest_contract.py`、`test_kb_search_contract.py`
- Day17：RAG Chat（同步 `/chat`）：
  - `use_kb/kb_top_k` 检索注入
  - `metadata.rag` 返回 citations
  - KB 空/异常降级，仍返回 200
- Day18：RAG Stream + Demo + KB 管理 + 契约测试：
  - `/chat/stream` 接入 RAG
  - Demo 增加 RAG 开关 + top_k 输入 + citations 展示
  - `GET /kb/documents`
  - `DELETE /kb/documents/{doc_id}` tombstone + Chroma 清理

### Day19：RAG KB 评测闭环 + KB Seed 清洗 + query-aware rerank

- 新增 `eval/qa_rag_20.jsonl`：20 条 QA 评测集。
- 新增 `scripts/eval_qa_rag.py`：调用 `/chat`，输出 `results.jsonl` 与 `summary.json`。
- 固化 `extract_index_text()`：只索引正文，遇到 `---` 或 `# Keywords/# QA Seeds/# Appendix/# Changelog` 截断。
- 新增/整理 `docs/kb_seed/01-11`，其中 `11_Environment & Ops.md` 覆盖 WSL/Windows/Ollama/本地 embedding 模型路径。
- 修复 RAG metadata 形状：KB 关闭/开启都用统一 rag 结构（通过 `enabled` 标识）。
- 引入 `KB_CANDIDATE_K=50` + `rerank_hits()` query-aware 专题加分。
- 修复 `answer_hit` 假阳性：对“不确定/需要更多上下文”等回答做拦截。
- 修复 rerank 过拟合：取消 RAG 文档无条件加分，改为 query 触发的 title/topic boost。
- 最终 QA20：answer_hit_rate=95%，citation_hit_rate=100%，effective_rag_rate=100%，avg_latency_ms≈1953ms。

### Day20：RAG Eval Report + Regression Gates + KB Seed 文档补全

- 新增 `scripts/build_eval_report.py`。
- 生成 `eval/reports/rag_eval_report.md`。
- strict regression gates：
  - `answer_hit_rate >= 0.90`
  - `citation_hit_rate >= 0.95`
  - `effective_rag_rate >= 0.95`
  - `title_hit_rate >= 0.85`
  - `p95_latency_ms <= 6000`
  - `failed_count == 0`
- 当前 report gate：PASS（answer=95%、citation=100%、effective_rag=100%、title=95%、p95≈3857ms）。
- 新增回归测试：
  - `tests/kb/test_index_text.py`
  - `tests/eval/test_eval_metrics_unit.py`
  - `tests/kb/test_rag_rerank.py`
- 全量测试：44 passed。
- 新增 KB Seed 源文档：
  - `docs/kb_seed/12_RAG Eval Report & Regression Gates.md`
  - `docs/kb_seed/13_Retrieval Rerank & Candidate Pool.md`
- 注意：12/13 先作为源文档提交，不急着入库，避免立即改变 QA20 召回分布。

### Day21：Demo Storyline 文档化

- 新增 `docs/demo_storyline_day22.md`。
- 规划 Day22 演示链路：
  - Health
  - PromptHub
  - RAG Sync
  - RAG Stream
  - A/B Compare
  - Replay
  - Error Demo
  - Eval Report
- Day21 只改文档，不改变 API/schema/RAG/SSE 逻辑，不需要新增契约测试；用现有 `pytest -q` 回归确认。

### Day22：Demo Storyline 全链路实跑

- `/health` 通过。
- `/prompts` 通过：`qa_strict:v1`、`chat:v1`。
- 重建 live KB 为 01-11 kb_seed，修复最初 live KB 只含 demo 文档导致 RAG 回答“不确定”的问题。
- RAG Sync Chat 通过：`docs.jsonl 的作用是什么？` 能返回项目语义答案，citations 指向 `KB Ingest & Search`。
- RAG Streaming SSE 通过：`meta → token* → usage → done`，usage.rag.citations 指向 `RAG in Chat/Stream`。
- Prompt A/B Compare 通过：返回 `compare_group_id`、A/B trace_id、latency/output diff。
- Replay 通过：`/runs/trace/{trace_id}` 与 `/runs/compare/{compare_group_id}` 均可回放。
- Error Demo 通过：
  - `/chat` 下游失败返回 502 structured detail
  - `/chat/stream` 下游失败返回 HTTP 200 + `event:error`
- Eval Report strict gate 通过。
- 恢复正常 Ollama 后 `/chat` 可用。
- `pytest -q`：44 passed。
- 清理运行时产物：`git restore kb/chroma kb/docs.jsonl kb/docs`，工作区 clean。

### Day23：CI + System Design，chat-api v1 工程化收口

- 新增 `requirements.txt`，为 CI 和新环境安装提供稳定依赖入口。
- 新增 GitHub Actions：`.github/workflows/ci.yml`，自动安装依赖并执行 `pytest -q`。
- 新增 `docs/system_design.md`：总结系统架构、同步/流式请求链路、RAG Pipeline、PromptHub/A/B Compare、Run Replay、错误处理、评测门槛、设计权衡与当前边界。
- 首次 CI 失败原因：`src/app/kb/embeddings.py` 顶层导入 `sentence_transformers`，导致 mock embedding 的 CI 也被迫依赖重型 HF 包。
- 修复方式：将 `sentence_transformers` 改为 HF provider 的懒加载；`EMBEDDING_PROVIDER=mock` 时不再需要安装 `sentence-transformers/torch/transformers`。
- 最新 GitHub Actions 通过。
- 本地测试保持：`pytest -q` 44 passed。
- Day23 不新增业务接口，也不改变 API contract；主要是 CI、依赖管理、架构文档和可维护性收口。
- chat-api v1 阶段性完结。

### Day24：LangChain RAG Backend Skeleton（v2 起点）

- 从 `master` 切出 v2 分支：`v2-langchain-rag`。
- 新增 `RAG_BACKEND=native|langchain` 配置，默认 `native`。
- 新增 `requirements-langchain.txt`，将 `langchain` 与 `langchain-ollama` 作为可选依赖，不污染主 `requirements.txt`。
- 新增 `src/app/rag/` 模块：
  - `base.py`：`RAGBackend` 抽象
  - `schemas.py`：`RAGCitation` / `RAGContextResult`
  - `native_backend.py`：封装现有 native RAG 检索链路
  - `langchain_backend.py`：LangChain skeleton + 依赖懒加载
  - `factory.py`：`get_rag_backend()`
- 新增 `tests/rag/test_rag_backend_factory.py`，覆盖：
  - 默认 backend 是 native
  - 非法 backend 抛清晰错误
  - langchain backend 未安装依赖时提示 `requirements-langchain.txt`
- 本地测试：
  - `pytest tests/rag/test_rag_backend_factory.py -q` → 3 passed
  - `pytest -q` → 47 passed
- CI 调整：`.github/workflows/ci.yml` 从只监听 `master` 改为所有分支 push 都跑，确保 v2 feature branch 也受 CI 保护。
- `v2-langchain-rag` 分支 GitHub Actions 通过。
- Day24 不接入 `/chat` 和 `/chat/stream` 主链路，只收一个稳定目标：可插拔 RAG backend 骨架 + factory 测试 + CI 通过。

### Day25：routes_chat.py 接入 RAGBackend

- 提交：`2c672b6`，message：`refactor(day25): route chat rag through backend`。
- 修改文件：`src/app/api/routes_chat.py`、`src/app/rag/native_backend.py`。
- `/chat` 与 `/chat/stream` 不再各自手写 embedding / Chroma / Hit / rerank / build_rag_context，而是统一调用：
  - `get_rag_backend().build_context(query=query, top_k=top_k)`
- route 层只负责把 `RAGContextResult` 转回原有 `RagMetadata` / SSE `rag` 结构，保持 API contract 不变。
- 新增 helper：
  - `build_rag_prompt_context(context_text)`：包装 backend context 为原有 system context。
  - `to_llm_citations(citations)`：把 `RAGCitation` 转回原有 `Citation` schema。
- 修复 `NativeRAGBackend.build_context()` 的真实运行问题：
  - `get_embedding_engine()` → `get_embedding_engine(settings)`。
  - `extra={"backend", "native"}` → `extra={"backend": "native"}`。
- 验收：
  - `pytest tests/chat/test_chat_rag_contract.py -q` → 2 passed
  - `pytest tests/stream/test_stream_rag_contract.py -q` → 2 passed
  - `pytest -q` → 47 passed
  - `python scripts/build_eval_report.py ... --strict` → All regression gates passed
  - GitHub Actions passed

### Day26：LangChain RAG Backend Retriever

- 提交 1：`c172523`，message：`feat(day26): implement langchain rag backend retrieval`。
- 提交 2：`1e19e3c`，message：`test(day26): assert langchain rag backend marker`。
- 修改/新增文件：
  - `requirements-langchain.txt`
  - `src/app/rag/langchain_backend.py`
  - `tests/rag/test_langchain_backend_contract.py`
- `requirements-langchain.txt` 当前包含：
  - `langchain`
  - `langchain-ollama`
  - `langchain-chroma`
- `RAG_BACKEND=langchain` 不再是 skeleton，已经能通过 `langchain_chroma.Chroma` 查询现有 Chroma KB。
- LangChain backend 复用项目自身 `get_embedding_engine(settings)`，将其包装成 LangChain `Embeddings` 接口，保证查询 embedding 与入库 embedding 保持同一向量空间。
- `LangChainRAGBackend.build_context()` 仍然输出统一的 `RAGContextResult`，其中 `extra` 包含：
  - `backend=langchain`
  - `vectorstore=langchain_chroma`
- 新增 `tests/rag/test_langchain_backend_contract.py`：
  - 验证 `RAG_BACKEND=langchain` 时 `/chat` 能真实命中 KB。
  - 直接调用 backend，断言 `result.extra["backend"] == "langchain"`。
  - 断言 `result.extra.get("vectorstore") == "langchain_chroma"`，防止误走 native backend。
- 本地验收：
  - `pytest tests/rag/test_langchain_backend_contract.py -q` → 2 passed
  - `RAG_BACKEND=langchain pytest tests/chat/test_chat_rag_contract.py -q` → 2 passed
  - `RAG_BACKEND=langchain pytest tests/stream/test_stream_rag_contract.py -q` → 2 passed
  - `pytest -q` → 49 passed
- 远程验收：GitHub Actions passed。
- 注意：LangChain / Chroma 测试会修改 `kb/chroma/chroma.sqlite3`，这是运行时产物，不应提交；提交前执行 `git restore kb/chroma/chroma.sqlite3`。

---

## 3. 当前状态（可用验收）

- 当前分支：`v2-langchain-rag`
- v1 主链路仍在 master 稳定可用。
- mock：`/health`、`/chat`、`/chat/stream`、`/demo`、`/prompt/compare`、`/prompts`、`/runs/*`、`/kb/*` 全部 OK。
- ollama：可达时 `/chat`、`/chat/stream`、`/prompt/compare` OK；不可达时 `/chat`=502(detail 结构化)，`/chat/stream`=200 + `event:error`。
- RAG：同步与流式均支持 `use_kb/kb_top_k`；citations 可追溯到 `doc_id/chunk_id/source/title`；Day25 后 `/chat` 与 `/chat/stream` 均通过统一 `RAGBackend` 构建上下文；Day26 后 `native/langchain` 双 backend 均可真实检索。
- 评测：`python scripts/eval_qa_rag.py --qa eval/qa_rag_20.jsonl --provider ollama` 可跑完 QA20，并输出 summary。
- 报告：`python scripts/build_eval_report.py ... --strict` 可生成 report，并在当前结果下通过 regression gates。
- 测试：`pytest -q` 当前 49 passed（包含 Day24 backend factory、Day25 route backend 接入、Day26 langchain backend contract 测试）。
- CI：master 与 v2 分支均可通过 GitHub Actions；Day26 两个提交 `c172523` 与 `1e19e3c` 已通过。
- Demo：`docs/demo_storyline_day22.md` 已经实跑验证，可作为面试演示脚本。

---

## 4. Day19–Day26 重要经验（面试可讲）

Day19–Day22 是完整的 RAG 工程排障、评测与演示闭环：

- API schema 不匹配：最初入库 payload 用 `markdown`，后端实际要求 `text`，导致 422；通过 OpenAPI 自检定位。
- Shell heredoc/curl 管道错误：多次出现 `syntax error near unexpected token |`，最终固定成稳定的 `python ... | curl -d @-` 入库模板。
- KB 清理方式错误：手动删除 `kb/docs/*.md` 会导致 API delete 找不到文件/状态不一致；后来统一通过 API tombstone + Chroma 清理。
- QA Seeds/Keywords 污染：评测题和关键词被索引后抢召回；通过 `extract_index_text` 只索引正文解决。
- 旧 Chroma 索引未更新：md 已修改但检索仍命中旧 chunk；通过清理 Chroma + 重新入库验证。
- `/kb/documents?limit=300` 返回 422：接口 limit 有上限，改为 200。
- `candidate_k/rerank/top_k` 正确 chunk 曾排在原始向量检索 rank20；通过 `KB_CANDIDATE_K=50` + query-aware rerank 拉回。
- rerank 一度过拟合，把所有题都吸到 `RAG in Chat/Stream`；改为“只有 query 命中特定主题词才给对应 title 加分”。
- answer_hit 假阳性：模型回答“不确定”但包含关键词，最初被误判通过；增加 uncertain 拦截。
- answer_hit 假阴性：业务语义“没有找到记录所以 404”被“不确定模式”误杀；收窄 uncertainty patterns。
- Report gate：从“控制台指标”升级到 `rag_eval_report.md` + `--strict`，为后续 CI/回归门槛做准备。
- Day22 live demo 暴露 live KB 状态问题：最初只命中 demo 文档导致 docs.jsonl 问题回答“不确定”；重建 kb_seed 后通过。
- Day22 验证了 raw `/kb/search` 与 `/chat` 的差异：裸检索 top5 不一定准，`/chat` 走 `candidate_k=50 + query-aware rerank` 后能拉回正确 chunk。
- Git hygiene：运行时产物 `kb/chroma/`、`kb/docs/`、`kb/docs.jsonl`、`eval/results/`、`eval/reports/` 不提交，只提交源码、KB seed 源文档、QA 集和评测脚本。

Day23–Day24 是工程化收口与 v2 架构扩展入口：

- CI 的价值不仅是跑测试，也是暴露“本地环境隐式依赖”的工具；本地能跑不代表新环境能跑。
- `sentence_transformers` 这类重依赖不能顶层 import，否则 mock 测试也会被迫依赖 HF 包；正确做法是 provider 内懒加载。
- `requirements.txt` 只保留基础服务与测试依赖，不把 `sentence-transformers/torch/transformers` 放入默认依赖，避免 CI 变慢。
- feature branch 也应触发 CI，否则 v2 开发无法获得远程自动验证。
- Day24 没有直接把 LangChain 硬塞进主链路，而是先做 backend 抽象：
  - 默认 native backend 保持已有行为不变
  - LangChain 作为可选 backend 懒加载
  - 后续 `/chat` 与 `/chat/stream` 只依赖统一 `RAGBackend` 接口
- 这样既保留手写 RAG 的可控性，也为后续 LangChain / Advanced RAG 扩展留出入口。
- Day25 的核心不是新增 RAG 能力，而是把 route 层从 RAG 细节中解耦：`routes_chat.py` 不再直接关心 embedding、Chroma、Hit、rerank、context 拼接，而是统一调用 `get_rag_backend().build_context()`。
- Day26 让 `RAG_BACKEND=langchain` 从 skeleton 变成真实 retriever，但没有替换项目 embedding 模型，而是把现有 `get_embedding_engine(settings)` 包装成 LangChain Embeddings，保证查询向量空间与入库向量空间一致。
- Day26 的 backend marker 测试直接断言 `RAGContextResult.extra["backend"] == "langchain"`，避免只通过接口结果误判为走了 langchain backend。
- 可选依赖测试使用 `pytest.importorskip` 保护 CI，避免基础 CI 被 LangChain 依赖污染。

---

## 5. Git hygiene

以下是运行时产物，不建议提交：

```gitignore
kb/chroma/
kb/docs/
kb/docs.jsonl
eval/results/
eval/reports/
eval/kb_seed_manifest.jsonl
backup_kb_reset/
.qoder/
```

建议提交：

- `src/**` 源码；
- `docs/kb_seed/*.md` 源文档；
- `docs/demo_storyline_day22.md` 演示脚本；
- `docs/system_design.md` 系统设计说明；
- `eval/qa_rag_20.jsonl` 评测集；
- `scripts/eval_qa_rag.py` / `scripts/build_eval_report.py`；
- `tests/**` 回归测试；
- `.github/workflows/ci.yml`；
- `requirements.txt` / `requirements-langchain.txt`；
- README / HANDOFF / day logs / weekly summaries。

---

## 6. 下一步（Day27）

Day27 主题：**RAG Observability：latency breakdown + trace 增强**。

建议任务：

1. 在 native / langchain backend 中记录统一 timing schema：
   - `embedding_ms`
   - `retrieval_ms`
   - `rerank_ms`
   - `context_build_ms`
   - `total_ms`
2. 将 timing 与 backend marker 放入 `RAGContextResult.extra`。
3. route 层透传到：
   - `/chat` 的 `metadata.rag`
   - `/chat/stream` 的 `meta.rag` / `usage.rag`
4. 新增/更新 contract tests：
   - timing 字段存在；
   - timing 字段为非负整数；
   - backend 字段能区分 `native/langchain`；
   - stream usage.rag 中 timing 字段存在。
5. 回归：
   - `pytest -q`
   - `RAG_BACKEND=langchain pytest tests/chat/test_chat_rag_contract.py -q`
   - `RAG_BACKEND=langchain pytest tests/stream/test_stream_rag_contract.py -q`
   - `python scripts/build_eval_report.py ... --strict`

Day27 暂不做 Hybrid Search / Query Rewrite / Reranker。先补齐 RAG pipeline 可观测性。
