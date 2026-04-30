开始新对话前：**“继续 chat-api 计划，从 Day15 开始（Prompt 列表 + 回放 API）。”**

# HANDOFF（给新对话用，更新至 Day14）
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

## 已完成进度（Day1–Day14）
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
- Day13：PromptHub 最小闭环：
  - Prompt Registry：`prompts/<prompt_id>/<version>.md`
  - `/chat` 与 `/chat/stream` 支持 `prompt_id/prompt_version/prompt_vars`（服务端注入 system prompt）
  - `meta/usage/error` 事件携带 prompt_id/version
  - run log（JSONL）落盘：trace_id/provider/model/latency_ms/token_events/prompt_id/prompt_version
  - Demo 增强：复制 trace_id / 复制 curl / 清空输出（配合 Stop/Abort）
- Day14：Prompt A/B Compare：
  - 新增 `POST /prompt/compare`：同一输入跑两套 prompt（A/B），返回并列结果 + 指标
  - run log（JSONL）新增：`compare_group_id + variant(A/B) + mode=compare`，并记录生成参数（temperature/top_p/max_tokens）
  - Demo 支持 Stream/Compare 模式切换，Compare 显示 group_id、A/B 输出、metrics，Copy Curl 可复现
  - 新增 compare 契约测试：`tests/test_prompt_compare_contract.py`
  - 离线回放工具：`scripts/replay_compare.py`（按 compare_group_id 回放 A/B）

## 当前状态（可用验收）
- mock：`/health`、`/chat`、`/chat/stream`、`/demo`、`/prompt/compare` 全部 OK
- ollama：可达时 `/chat`、`/chat/stream`、`/prompt/compare` OK；不可达时 `/chat`=502(detail 结构化)，`/chat/stream`=200 + `event:error`

## 下一步（Day15）
- `GET /prompts`：列出 prompt_id 与版本（扫描 prompts 目录）
- `GET /runs/{trace_id}`：按 trace_id 回放查询（从 JSONL 查）
- `GET /runs/compare/{compare_group_id}`：按 group 回放查询（将 replay 能力 API 化）
- README 收尾：补齐 PromptHub/Compare/Replay 的使用与演示步骤
