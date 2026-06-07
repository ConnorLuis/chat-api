开始新对话前：**“继续 chat-api 计划，从 Day21 开始（扩展 KB Seed 到 13 篇并跑 QA20 回归 / 继续补全 KB Seed 文档）。”**

# HANDOFF（给新对话用，更新至 Day20）

## 0. 环境与项目

- 环境：WSL2 Ubuntu + conda env=`chatapi` (Python 3.10)
- 项目：`~/projects/chat-api`（GitHub: ConnorLuis/chat-api，branch `master`）
- Ollama：安装在 Windows；模型 `qwen2.5:7b` 已 pull
- WSL 访问 Windows Ollama：

```bash
WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"
```

已写入 `~/.bashrc`。

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
- `EMBEDDING_PROVIDER`（默认 `mock`，可选 `mock|hf`）
- `EMBEDDING_MODEL`（HF embedding 模型路径/名称）
- `EMBEDDING_DIM`（mock embedding 维度）

## 2. 已完成进度（Day1–Day20）

- Day1：`GET /health` OK
- Day2：`POST /chat`（mock + schemas）、全局中间件（`x-trace-id` + latency log）、`POST /chat/stream`（mock streaming）OK
- Day3：可插拔引擎 `LLMEngine`（mock/ollama）；`ChatRequest` 增加 `provider=mock|ollama`
- Day4：补齐 `README.md`；新增 pytest（`/health`、`/chat mock`）；修复测试导入路径（`tests/conftest.py`）
- Day5：`/chat/stream` 升级为 SSE（`text/event-stream`），事件：`meta/token/done/error`
- Day6：SSE 标准化增强：`sse_event`（data 字符串化/JSON 序列化/多行）、新增 `event: usage`、结构化 `event: error`
- Day7：同步接口对齐：`settings.py`（env 读取）；`ChatResponse.metadata`（provider/model/latency_ms）；契约测试 `test_chat_contract.py`
- Day8：错误与日志工程化：`build_error()` 统一 502 detail 与 stream error；meta 增加 model；model 兜底为 `unknown`
- Day9：README 增补；新增 SSE/stream 契约测试（事件块 `\n\n`、顺序 meta→token*→usage→done）
- Day10：OpenAPI `/docs` 增强：schemas examples + 路由 summary/description/responses
- Day11：新增 `/demo` 流式聊天演示页（fetch POST + ReadableStream 解析 SSE）
- Day12：Demo 增强 Stop/Abort（AbortController）；AbortError 不视为业务错误
- Day13：PromptHub 最小闭环：prompt_id/version + run log + demo 增强
- Day14：Prompt A/B Compare：`POST /prompt/compare` + run log compare_group_id + demo compare 模式 + replay 工具 + 契约测试
- Day15：PromptHub Query APIs：
  - `GET /prompts`：扫描 prompts 目录，列出 prompt_id 与版本
  - `GET /runs/trace/{trace_id}`：按 trace_id 回放查询（找不到 404；返回 records + bad_lines）
  - `GET /runs/compare/{compare_group_id}`：按 group 回放 A/B（A/B 排序 + summary；bad_lines 容错）
- Day16：RAG KB 最小闭环（Chroma）：
  - `POST /kb/documents`：入库（save → chunk → embedding → Chroma upsert）
  - `GET /kb/search`：topK 检索返回 hits（doc_id/chunk_id/score/text/source/title）
  - 契约测试：`test_kb_ingest_contract.py`、`test_kb_search_contract.py`
- Day17：RAG Chat（同步 `/chat`）：
  - `use_kb/kb_top_k` 检索注入；响应 `metadata.rag` 返回结构化 citations
  - 降级：KB 空/异常仍 200，citations=[]、hits=0；run log 记录 `rag_error/context_chars`
  - 契约测试：`tests/chat/test_chat_rag_contract.py`
- Day18：RAG Stream + Demo + KB 管理 + 契约测试
  - `/chat/stream` 接入 RAG：`meta/usage/error` 带 `rag`（enabled/top_k/hits/context_chars/citations/error）
  - Demo：增加 RAG 开关 + top_k 输入 + 引用展示；修复 SSE 解析（CRLF/data: 兼容、完整块解析）；修复 Copy Curl 续行
  - KB 管理：`GET /kb/documents`（limit/offset/include_deleted），`DELETE /kb/documents/{doc_id}`（Chroma delete + md delete + tombstone）
  - 新增契约测试：demo/stream/kb；`pytest -q` 全绿：**30 passed**
- Day19：RAG KB 评测闭环 + KB Seed 清洗 + query-aware rerank
  - 新增 `eval/qa_rag_20.jsonl`：20 条 QA 评测集
  - 新增 `scripts/eval_qa_rag.py`：调用 `/chat`，输出 `results.jsonl` 与 `summary.json`
  - 固化 `extract_index_text()`：只索引正文，遇到 `---` 或 `# Keywords/# QA Seeds/# Appendix/# Changelog` 截断
  - 新增/整理 `docs/kb_seed/01-11`，其中 `11_Environment & Ops.md` 覆盖 WSL/Windows/Ollama/本地 embedding 模型路径
  - 修复 RAG metadata 形状：KB 关闭/开启都用统一 rag 结构（通过 `enabled` 标识）
  - 引入 `KB_CANDIDATE_K=50` + `rerank_hits()` query-aware 专题加分
  - 修复 `answer_hit` 假阳性：对“不确定/需要更多上下文”等回答做拦截
  - 修复 rerank 过拟合：取消 RAG 文档无条件加分，改为 query 触发的 title/topic boost
  - 最终 QA20：**answer_hit_rate=95%，citation_hit_rate=100%，effective_rag_rate=100%，avg_latency_ms≈1953ms**
- **Day20：RAG Eval Report + Regression Gates + KB Seed 文档补全**
  - 新增 `scripts/build_eval_report.py`：读取 `eval/results/rag_eval_20.jsonl` 与 summary，生成 `eval/reports/rag_eval_report.md`
  - 增加 strict regression gates：`answer_hit_rate>=0.90`、`citation_hit_rate>=0.95`、`effective_rag_rate>=0.95`、`title_hit_rate>=0.85`、`p95_latency_ms<=6000`、`failed_count==0`
  - 当前 report gate 验收：**PASS**（answer=95%、citation=100%、effective_rag=100%、title=95%、p95≈3857ms）
  - 新增 Day19/Day20 回归测试：`tests/kb/test_index_text.py`、`tests/eval/test_eval_metrics_unit.py`、`tests/kb/test_rag_rerank.py`
  - 全量测试：**44 passed**
  - 新增 KB Seed 源文档：
    - `docs/kb_seed/12_RAG Eval Report & Regression Gates.md`
    - `docs/kb_seed/13_Retrieval Rerank & Candidate Pool.md`
  - 注意：12/13 目前建议先作为源文档提交，下一步再决定是否入库，避免立即改变 QA20 召回分布。

## 3. 当前状态（可用验收）

- mock：`/health`、`/chat`、`/chat/stream`、`/demo`、`/prompt/compare`、`/prompts`、`/runs/*`、`/kb/*` 全部 OK
- ollama：可达时 `/chat`、`/chat/stream`、`/prompt/compare` OK；不可达时 `/chat`=502(detail 结构化)，`/chat/stream`=200 + `event:error`
- RAG：同步与流式均支持 `use_kb/kb_top_k`；citations 可追溯到 `doc_id/chunk_id/source/title`
- 评测：`python scripts/eval_qa_rag.py --qa eval/qa_rag_20.jsonl --provider ollama` 可跑完 QA20，并输出 summary
- 报告：`python scripts/build_eval_report.py ... --strict` 可生成 report，并在当前结果下通过 regression gates
- 测试：`pytest -q` 当前 **44 passed**

## 4. Day19/Day20 重要经验（面试可讲）

Day19–Day20 是一次完整的 RAG 工程排障与评测闭环：

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
- Git hygiene：运行时产物 `kb/chroma/`、`kb/docs/`、`kb/docs.jsonl`、`eval/results/`、`eval/reports/` 不提交，只提交源码、KB seed 源文档、QA 集和评测脚本。

## 5. 下一步（Day21）

- 决定是否将 12/13 纳入 KB 入库；若入库，需要重建/增量入库后重新跑 QA20 回归。
- 继续补全 `docs/kb_seed` 剩余主题文档，建议方向：部署/CI、性能与观测、PromptHub 进阶、RAG 失败案例、面试讲解版。
- 将 `build_eval_report.py --strict` 接入本地回归流程，必要时再考虑 CI。
- 按 Git hygiene 检查提交：不提交 `kb/chroma/`、`kb/docs/`、`eval/results/`、`eval/reports/`。
