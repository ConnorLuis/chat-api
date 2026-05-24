开始新对话前：**“继续 chat-api 计划，从 Day18 开始（Stream RAG + Demo RAG + KB 管理 + 契约测试）。”**

# HANDOFF（给新对话用，更新至 Day18）
- 环境：WSL2 Ubuntu + conda env=chatapi (Python 3.10)
- 项目：`~/projects/chat-api`（GitHub: ConnorLuis/chat-api，branch master）
- Ollama：安装在 Windows；模型 `qwen2.5:7b` 已 pull
- WSL 访问 Windows Ollama：
  - `WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')`
  - `export OLLAMA_BASE_URL="http://$WIN_IP:11434"`（已写入 `~/.bashrc`）
- 关键环境变量（均支持覆盖）：
  - `OLLAMA_BASE_URL`（默认 `http://127.0.0.1:11434`）
  - `OLLAMA_MODEL`（默认 `qwen2.5:7b`）
  - `OLLAMA_TIMEOUT_S`（默认 `60`）
  - `RUN_LOG_PATH`（默认 `runs/prompt_runs.jsonl`）

## 已完成进度（Day1–Day18）
- Day1：`GET /health` OK
- Day2：`POST /chat`（mock + schemas）、全局中间件（`x-trace-id` + latency log）、`POST /chat/stream`（mock streaming）OK
- Day3：可插拔引擎 `LLMEngine`（mock/ollama）；`ChatRequest` 增加 `provider=mock|ollama`
- Day4：补齐 `README.md`；新增 pytest（`/health`、`/chat mock`）；修复测试导入路径（`tests/conftest.py`）
- Day5：`/chat/stream` 升级为 SSE（`text/event-stream`），事件：`meta/token/done/error`
- Day6：SSE 标准化增强：`sse_event`（data 字符串化/JSON 序列化/多行）、新增 `event: usage`、结构化 `event: error`
- Day7：同步接口对齐：`settings.py`（env 读取）；`ChatResponse.metadata`（provider/model/latency_ms）；契约测试 `test_chat_contract.py`
- Day8：错误与日志工程化：`build_error()` 统一 502 detail 与 stream error；meta 增加 model；model 兜底为 `unknown`
- Day9：README 增补；新增 SSE/stream 契约测试（事件块 `\n\n`、顺序 meta→token*→usage→done）
- Day10：OpenAPI /docs 增强：schemas examples + 路由 summary/description/responses
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
- **Day18：RAG Stream + Demo + KB 管理 + 契约测试（本次新增）**
  - `/chat/stream` 接入 RAG：`meta/usage/error` 带 `rag`（enabled/top_k/hits/context_chars/citations/error）
  - Demo：增加 RAG 开关 + top_k 输入 + 引用展示；修复 SSE 解析（CRLF/data: 兼容、完整块解析）；修复 Copy Curl 续行
  - KB 管理：`GET /kb/documents`（limit/offset/include_deleted），`DELETE /kb/documents/{doc_id}`（Chroma delete + md delete + tombstone）
  - 新增契约测试：demo/stream/kb（Day18 相关）
  - `pytest -q` 全绿：**30 passed**

## 当前状态（可用验收）
- mock：`/health`、`/chat`、`/chat/stream`、`/demo`、`/prompt/compare`、`/prompts`、`/runs/*`、`/kb/*` 全部 OK
- ollama：可达时 `/chat`、`/chat/stream`、`/prompt/compare` OK；不可达时 `/chat`=502(detail 结构化)，`/chat/stream`=200 + `event:error`

## 下一步（Day19）
- 最小评测脚本（20 条 QA）：输出准确率/引用命中率/延迟（先粗糙也行）。
- 或者 KB 文档列表在 demo 上做一个只读展示（可选）。
