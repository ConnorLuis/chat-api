开始新对话前：**“继续 chat-api 计划，从 Day12 开始。”**

# HANDOFF（给新对话用，更新至 Day11）
- 环境：WSL2 Ubuntu + conda env=chatapi (Python 3.10)
- 项目：`~/projects/chat-api`（GitHub: ConnorLuis/chat-api，branch master）
- Ollama：安装在 Windows；模型 `qwen2.5:7b`（Q4_K_M）已 pull
- WSL 访问 Windows Ollama：
  - `WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')`
  - `export OLLAMA_BASE_URL="http://$WIN_IP:11434"`（已写入 `~/.bashrc`）
- 关键环境变量（均支持覆盖）：
  - `OLLAMA_BASE_URL`（默认 `http://127.0.0.1:11434`）
  - `OLLAMA_MODEL`（默认 `qwen2.5:7b`）
  - `OLLAMA_TIMEOUT_S`（默认 `60`）

## 已完成进度（Day1–Day11）
- Day1：`GET /health` OK
- Day2：`POST /chat`（mock + schemas）、全局中间件（`x-trace-id` + latency log）、`POST /chat/stream`（mock streaming）OK
- Day3：可插拔引擎 `LLMEngine`（mock/ollama）；`ChatRequest` 增加 `provider=mock|ollama`；WSL -> Windows Ollama 链路打通
- Day4：补齐 `README.md`；新增 pytest（`/health`、`/chat mock`）；修复测试导入路径（`tests/conftest.py`）
- Day5：`/chat/stream` 升级为 SSE（`text/event-stream`），事件：`meta/token/done/error`；新增 SSE 测试
- Day6：SSE 标准化增强：
  - `sse_event`：data 统一转字符串（结构化自动 JSON 序列化），并支持多行 data
  - 新增 `event: usage`（provider/model/latency_ms/token_events）
  - `event: error` 统一结构化 JSON（含 trace_id/provider/model/latency_ms/error）
  - 新增测试：usage 存在；ollama 不可达时仍 200 但 SSE 返回 error
- Day7：同步接口对齐：
  - 新增 `settings.py`（property 动态读取 env）
  - `ChatResponse` 增加 `metadata`（provider/model/latency_ms）
  - 新增契约测试 `test_chat_contract.py`
- Day8：错误与日志工程化：
  - 新增 `build_error()`，统一 `/chat` 的 502 detail 与 SSE 的 `event:error` 的结构化 JSON（trace_id/provider/model/latency_ms/error）
  - logging 初始化（main 中 setup），中间件/路由统一 logger 输出（trace_id/provider/model/latency_ms）
  - 新增错误契约测试：`/chat` 502 结构稳定；`/chat/stream` error event 结构稳定
  - `meta` 事件增加 `model`，并统一 `model` 兜底为 `"unknown"`
- Day9：文档与 SSE 契约测试增强：
  - README 增补：Error Handling Contract、SSE event format、Runtime debugging（含“改 env 需重启服务”坑）
  - 新增 `tests/test_sse_format.py`（事件块 `\n\n` 空行结束 + event/data 行存在）
  - 新增 `tests/test_stream_success_contract.py`（mock 成功流顺序：meta → token* → usage → done）
  - 修复测试路径误用反斜杠导致 404（`\chat\stream` → `/chat/stream`）
- Day10：OpenAPI /docs 增强：
  - `schemas.py`：`ChatRequest/ChatResponse/ErrorResponse` 补 examples（/docs 可直接看到示例）
  - `routes_chat.py`：为 `/chat`、`/chat/stream` 补 `summary/description/responses`，并使用 `Body(openapi_examples=...)` 提供可执行示例
  - 修复 Swagger Execute 出现 422：将 OpenAPI wrapper examples 从 schema 移到 `Body(openapi_examples=...)`
- Day11：新增 `/demo` 流式聊天演示页（可面试现场演示）：
  - 新增 `src/app/api/routes_demo.py`：`GET /demo` 返回内联 HTML + JS
  - Demo 通过 `fetch(POST /chat/stream)` 读取 `ReadableStream` 解析 SSE（不用 EventSource，因为 EventSource 只支持 GET）
  - Demo UI 展示：meta（trace_id/provider/model）、output（token 拼接）、usage、error、done
  - 新增 `tests/test_demo_page.py`：校验 `/demo` 返回 200 + `text/html`，并包含 SSE 关键字；全套测试通过（11 passed）

## 当前状态（可用验收）
- mock：
  - `/health` OK
  - `/chat` OK（含 metadata）
  - `/chat/stream` SSE OK（meta/token/usage/done；失败时 meta/error）
  - `/demo` OK（能流式展示 meta/output/usage/done）
- ollama：
  - `/chat` OK（含 metadata，model 正确；不可达时 502 + detail 结构化）
  - `/chat/stream` SSE OK（meta/token/usage/done；不可达时 meta/error 结构化）
  - `/demo` OK（能展示 model，例如 `qwen2.5:7b`）

## 下一步（Day12）
- Demo 增加 Stop/Abort（AbortController），可以随时中断流式请求并清理状态
- 可选：usage 统计增强（input/output token；或至少在 mock 模拟输出 token 计数）
- 可选：README 增加 Demo 截图（更直观）
