开始新对话前：“继续 chat-api 计划，从 Day？ 开始。”

# HANDOFF（给新对话用）
- 环境：WSL2 Ubuntu + conda env=chatapi (Python 3.10)
- 项目：`~/projects/chat-api`（GitHub: ConnorLuis/chat-api，branch master）
- Ollama：安装在 Windows；模型 `qwen2.5:7b`（Q4_K_M）已 pull
- WSL 访问 Windows Ollama：
  - `WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')`
  - `export OLLAMA_BASE_URL="http://$WIN_IP:11434"`（已写入 `~/.bashrc`）
- 关键环境变量：
  - `OLLAMA_BASE_URL`（默认 `http://127.0.0.1:11434`）
  - `OLLAMA_MODEL`（默认 `qwen2.5:7b`）
  - `OLLAMA_TIMEOUT_S`（默认 `60`）

## 已完成进度
- Day1：`GET /health` OK
- Day2：`POST /chat`（mock + schemas）、全局中间件（`x-trace-id` + latency log）、`POST /chat/stream`（mock streaming）OK
- Day3：可插拔引擎 `LLMEngine`（mock/ollama）；`ChatRequest` 增加 `provider=mock|ollama`；WSL -> Windows Ollama 链路打通
- Day4：补齐 `README.md`；Ollama 配置 env 化；新增 pytest（`/health`、`/chat mock`）；修复测试导入路径（`tests/conftest.py`）；`pytest -q` 通过
- Day5：`/chat/stream` 升级为 SSE（`text/event-stream`），事件类型：`meta/token/done/error`；新增 `src/app/core/sse.py`；新增 SSE 测试；`pytest -q` 3 passed

## 当前状态（可用验收）
- mock：
  - `/chat` OK
  - `/chat/stream` SSE OK
- ollama：
  - `/chat` OK
  - `/chat/stream` SSE OK

## 下一步（Day6 任务）
- SSE 产品化增强：
  - 新增 `event: usage`（provider/model/latency/token_events）
  - 统一 `event: error` 为结构化 JSON（含 trace_id/provider/model/latency）
  - 增加 2 个测试：usage 事件存在；ollama 不可达时返回 error 事件
  - README 增加 SSE 事件说明

