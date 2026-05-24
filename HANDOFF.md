开始新对话前：**“继续 chat-api 计划，从 Day18 开始（Demo RAG + Stream RAG + KB 管理）。”**

# HANDOFF（给新对话用，更新至 Day17）
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

## 已完成进度（Day1–Day15）
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
  - 新增 3 个 Day15 契约测试；pytest 全绿（21 passed）

- Day16：RAG KB 最小闭环（Chroma）：
  - `POST /kb/documents`：文本/markdown 入库（save → chunk → embedding → Chroma upsert），返回 `doc_id/chunks/metadata(trace_id,latency_ms)`
  - `GET /kb/search`：topK 检索返回 `hits`（doc_id/chunk_id/score/text/source/title）+ `metadata(trace_id,latency_ms)`
  - 配置项：`KB_DIR/KB_CHROMA_DIR/KB_COLLECTION/KB_CHUNK_SIZE/KB_CHUNK_OVERLAP/EMBEDDING_PROVIDER/EMBEDDING_MODEL/EMBEDDING_DIM`
  - 新增契约测试：`test_kb_ingest_contract.py`、`test_kb_search_contract.py`（含 empty query 400）
  - pytest 全绿（24 passed）

- Day17：RAG Chat 集成（同步）：
  - `/chat` 新增 `use_kb` + `kb_top_k`：检索 KB topK → context 注入 system prompt → 生成回答
  - 响应 `metadata.rag` 返回结构化 citations（doc_id/chunk_id/source/title）与 hits 数
  - 降级策略：query 为空 / KB 异常时 citations=[]、hits=0，chat 仍可用；run log 记录 `rag_error/context_chars`
  - 新增契约测试：`tests/chat/test_chat_rag_contract.py`
  - 整理 tests 目录：按领域拆分 `tests/chat|stream|kb|prompt|runs|demo|core`
  - pytest 全绿（26 passed）


## 当前状态（可用验收）
- mock：`/health`、`/chat`、`/chat/stream`、`/demo`、`/prompt/compare`、`/prompts`、`/runs/*` 全部 OK
- ollama：可达时 `/chat`、`/chat/stream`、`/prompt/compare` OK；不可达时 `/chat`=502(detail 结构化)，`/chat/stream`=200 + `event:error`

## 下一步（Day18）
- Demo 增强：/demo 增加 RAG 开关 + top_k 输入框 + 引用展示（优先做）
- 流式接入：把 RAG 接入 `/chat/stream`（meta/usage/done 中体现 rag 信息，并写 run log）
- KB 管理：新增 `/kb/documents` 列表与删除（为评测/运维铺路）
