# chat-api

<!-- LLM_GATEWAY_PLUS_START -->
## v2-plus Upgrade Positioning

`chat-api` 已从完成的 `v2-langchain-rag` 基线进入升级分支：

```text
v2-langchain-rag-plus
```

当前定位：

```text
Production-ready LLM Chat Gateway / 多模型统一接入与流式对话后端系统
```

### 项目边界

`agent-api` 已覆盖复杂 Agent 系统能力：

```text
Agentic RAG
GraphRAG
Multi-Agent
MCP Integration Layer
```

因此 `chat-api` 后续不重复建设复杂 Agent Graph、GraphRAG、Multi-Agent Supervisor、MCP 平台化或 `agent-api` 风格的 Agent 编排系统，而是聚焦生产级 LLM Chat Backend 工程能力。

### v2-plus 目标能力

```text
多 Provider 接入
OpenAI-compatible /v1/chat/completions
OpenAI-compatible SSE streaming
会话管理
消息持久化
上下文窗口截断
Token usage 统计
成本估算
API Key 鉴权
限流与 token quota
Prompt cache
Provider fallback / retry / timeout
结构化日志
trace_id 请求追踪
health / readiness
Docker / docker-compose 部署
测试与 CI
压测记录
API 文档
前端可接入
```

### 当前进度

```text
Chat-Day1:
  完成分支创建、项目定位、README/HANDOFF 更新、本地路线图和 anti-drift 规则。

Chat-Day2:
  完成 ChatProvider 抽象、Mock/Ollama/OpenAI Provider、ProviderFactory、
  请求级 provider/model override，以及 /chat、/chat/stream、/prompt/compare 主链路迁移。

Chat-Day3:
  完成非流式 OpenAI-compatible /v1/chat/completions、
  独立 request/response/error schema、provider override 和 OpenAI SDK 客户端兼容验证。

Chat-Day4:
  完成 /v1/chat/completions 的 OpenAI-compatible SSE streaming，
  支持 chat.completion.chunk、choices[].delta、finish_reason、
  可选 usage chunk、data: [DONE] 和流内 error，并保持旧 /chat/stream 契约不变。

Chat-Day5:
  完成 SQLAlchemy 2.x 持久化基础、SQLite 开发存储与 PostgreSQL 迁移边界、
  Conversation / Message ORM、session、repository/service、外键级联与隔离测试。

Chat-Day6:
  完成 Conversation HTTP API、conversation_id 请求/响应边界、
  稳定 sequence_no、历史加载、上下文窗口截断、同步/流式成功原子落库，
  以及 Provider 失败或客户端断开时不保存不完整消息。

Current validation:
  pytest tests/chat -q -> 14 passed
  pytest tests/conversations -q -> 7 passed
  pytest tests/db -q -> 14 passed
  pytest tests/stream -q -> 16 passed
  pytest tests/openai_compat -q -> 12 passed
  pytest -q -> 126 passed
  GitHub Actions CI -> success
  commit -> d60c5e3

Local-only roadmap:
  LLM_GATEWAY_ROADMAP.md，不进入 git。
```

### 下一步

```text
Chat-Day7:
  设计并实现请求级 Token usage 记录，
  明确同步、流式、Provider 原生 usage 与估算 usage 的统一边界。
```
<!-- LLM_GATEWAY_PLUS_END -->


一个最小可用的 FastAPI 聊天服务（工程化训练用），支持：

* `GET /health`：健康检查
* `POST /chat`：同步聊天（`provider=mock|ollama|openai`），支持请求级 `model` override，返回 `metadata`
* `POST /chat/stream`：SSE 流式聊天（`provider=mock|ollama|openai`），事件：`meta/token/usage/done/error`
* `POST /prompt/compare`：通过统一 Provider 层执行 Prompt A/B Compare
* `POST /v1/chat/completions`：OpenAI-compatible Chat Completions，支持非流式 `chat.completion` 与流式 `chat.completion.chunk`，并支持网关 `provider` override
* Conversation persistence：SQLAlchemy 2.x、SQLite、Conversation / Message、repository/service、稳定消息顺序与隔离测试
* Multi-conversation history：`conversation_id`、历史加载、最近 N 轮 / token budget 截断
* Conversation API：创建、列表、查询、重命名、删除与消息分页查询
* Persistence semantics：同步/流式仅在完整成功后原子保存本轮 user/assistant；失败或客户端断开不保存半轮消息
* 全局中间件：`x-trace-id` + latency 日志
* 统一 ChatProvider：MockProvider / OllamaProvider / OpenAIProvider
* ProviderFactory：屏蔽不同模型服务调用差异，OpenAI SDK 按需懒加载
* RAG：KB 入库/检索、同步/流式上下文注入、citations 溯源
* RAG backend abstraction：`RAG_BACKEND=native|langchain`；`/chat` 与 `/chat/stream` 已统一通过 backend 构建 RAG 上下文，LangChain backend 已支持真实检索，并暴露 RAG observability timing
* Hybrid RAG：vector retrieval + lexical scoring + fusion rerank，并在 `metadata.rag` / SSE `rag` 中暴露 retrieval_mode/fusion/weights
* KB 管理：文档列表、软删除 tombstone、Chroma 向量清理
* RAG 评测：QA20 离线评测、answer/citation/effective_rag/latency 指标
* RAG eval workflow：`seed_kb.py` + `run_rag_eval_workflow.py`，支持可复现 seed/eval/report strict gate
* v2 收口文档：`docs/system_design.md`、`docs/v2_demo_guide.md`、`docs/interview_talk_track.md`
* pytest：基础回归 + SSE 契约测试 + 错误契约测试

---

## Requirements

* Python 3.10+
* 推荐：WSL2 Ubuntu + conda
* 可选：Windows 安装 Ollama（用于本地大模型）

---

## Quick Start

### 1) Activate env & install deps

```bash
conda activate chatapi
python -m pip install -r requirements.txt
```


### Optional: LangChain backend dependencies (Day24 / v2)

Day24 新增可插拔 RAG backend skeleton。默认仍使用 native backend；如果后续要启用 LangChain backend，再单独安装：

```bash
python -m pip install -r requirements-langchain.txt
```

当前可选依赖文件：

```text
requirements-langchain.txt
```

包含：

```text
langchain
langchain-ollama
langchain-chroma
```

主 `requirements.txt` 不包含 LangChain，避免 CI 和基础测试被可选依赖污染。

### Optional: OpenAI Provider / SDK dependencies (Chat-Day2–Chat-Day4)

OpenAI / OpenAI-compatible Provider 使用可选依赖：

```bash
python -m pip install -r requirements-openai.txt
```

当前可选依赖文件：

```text
requirements-openai.txt
```

`openai` SDK 在 `OpenAIProvider` 真正执行请求时才懒加载，因此基础 CI、MockProvider 和 OllamaProvider 不依赖 OpenAI SDK。Chat-Day3 完成非流式 SDK 兼容验证，Chat-Day4 完成 `stream=True` 流式客户端验证；本地验证版本为 `openai 2.45.0`。

### 2) Run server

```bash
cd ~/projects/chat-api
python -m uvicorn src.app.main:app --reload --port 8000
```

### 3) Health check

```bash
curl http://localhost:8000/health
```

---

## Environment variables

* `OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
* `OLLAMA_MODEL` (default: `qwen2.5:7b`)
* `OLLAMA_TIMEOUT_S` (default: `60`)
* `OPENAI_API_KEY`：OpenAI / OpenAI-compatible Provider API key
* `OPENAI_BASE_URL`：可选 OpenAI-compatible endpoint
* `OPENAI_MODEL`：OpenAI Provider 默认模型；请求体 `model` 优先级更高
* `OPENAI_TIMEOUT_S` (default: `60`)
* `OPENAI_COMPAT_DEFAULT_PROVIDER` (default: `mock`)：`/v1/chat/completions` 未传网关扩展字段 `provider` 时使用的默认 Provider
* `DATABASE_URL` (default: `sqlite:///./data/chat_api.db`)：Conversation / Message 关系数据库连接地址；未来可切换 PostgreSQL
* `CONVERSATION_HISTORY_MAX_TURNS` (default: `10`)：最多保留的最近 user-led 历史轮数
* `CONVERSATION_CONTEXT_TOKEN_BUDGET` (default: `4096`)：历史 + 当前请求 + system prompt 的估算 token 上限
* `CONVERSATION_HISTORY_FETCH_LIMIT` (default: `500`)：从数据库读取的最大历史消息条数
* `RUN_LOG_PATH` (default: `runs/prompt_runs.jsonl`)
* `KB_DIR` (default: `kb`)
* `KB_CHROMA_DIR` (default: `${KB_DIR}/chroma`)
* `KB_TOP_K` (default: `5`)
* `KB_CANDIDATE_K` (default: `50`)：先召回更大候选池，再 rerank 截断到 `kb_top_k`
* `RAG_BACKEND` (default: `native`, options: `native|langchain`)：Day24 新增 backend skeleton；Day25 接入 `/chat` 与 `/chat/stream`；Day26 已实现 LangChain Chroma retriever；Day27 暴露 observability；Day28 使用 Hybrid fusion rerank
* `EMBEDDING_PROVIDER` (default: `mock`, options: `mock|hf`)
* `EMBEDDING_MODEL`：HF embedding 模型名或本地路径

### WSL2 -> Windows Ollama

如果 Ollama 安装在 Windows，WSL 需要用 Windows 网关 IP 访问：

```bash
WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"
```

---

## Multi-Provider Architecture (Chat-Day2)

Chat-Day2 将原有 `LLMEngine` 字符串返回接口升级为统一 Provider 层：

```text
HTTP API / Prompt Compare
        ↓
build_provider_request()
        ↓
ProviderFactory
        ↓
ChatProvider Protocol
  ├── MockProvider
  ├── OllamaProvider
  └── OpenAIProvider
```

Provider 内部统一结构：

```text
ProviderMessage
ProviderChatRequest
ProviderChatResponse
ProviderChatChunk
ProviderUsage
```

主调用链：

```text
POST /chat
  → get_chat_provider()
  → provider.chat()

POST /chat/stream
  → get_chat_provider()
  → provider.stream()

POST /prompt/compare
  → get_chat_provider()
  → provider.chat()
```

设计约束：

- API 层 `ChatRequest` 与 Provider 内部请求模型分离，RAG、PromptHub、session 等业务字段不下沉到 Provider。
- `model` 采用请求级覆盖；为空时使用 Provider 默认模型，仍无法解析时返回 `"unknown"` 或明确配置错误。
- MockProvider 无网络依赖，用于 deterministic tests 和 CI。
- OllamaProvider 继续使用现有 `/api/generate` 协议，避免在 Provider 重构时同时改变模型协议。
- OpenAIProvider 支持 OpenAI / OpenAI-compatible endpoint，SDK 懒加载，缺少 API key 时沿用现有 502 错误契约。
- 旧 `src/app/llm/engines/` 暂时保留为历史兼容代码；当前聊天业务入口已迁移到 `src/app/llm/providers/`。

---

## OpenAI-compatible Chat Completions (Chat-Day3 / Chat-Day4)

统一入口：

```text
POST /v1/chat/completions
```

该接口是独立协议兼容层，直接复用 Chat-Day2 的 `ChatProvider` 与 `ProviderFactory`，不会调用旧 `/chat` 或 `/chat/stream` 路由，也不会把 RAG、PromptHub、Replay 或旧 metadata 契约耦合进 OpenAI-compatible API。

### 当前支持范围

```text
stream=false → chat.completion
stream=true  → text/event-stream + chat.completion.chunk
单 choice：n=1
纯文本 messages
roles：developer / system / user / assistant
model / temperature / top_p
max_tokens / max_completion_tokens
stream_options.include_usage
可选网关扩展字段 provider=mock|ollama|openai
```

当前暂不支持：

```text
tools / tool_calls / function
多模态 content parts
n > 1
真实 logprobs 计算
response_format
```

### Non-stream request

```bash
curl -s -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mock-compatible-model",
    "messages": [
      {
        "role": "user",
        "content": "hello from curl"
      }
    ]
  }' | python -m json.tool
```

### Non-stream response

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1783671773,
  "model": "mock-compatible-model",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "[mock] you said: hello from curl"
      },
      "finish_reason": "stop",
      "logprobs": null
    }
  ]
}
```

当 Provider 返回完整 `prompt_tokens/completion_tokens/total_tokens` 时，接口返回 `usage`；未知用量不会伪造为零，而是省略该字段。

### Streaming request

```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "mock",
    "model": "mock-stream-model",
    "messages": [
      {
        "role": "user",
        "content": "hello day4"
      }
    ],
    "stream": true
  }'
```

响应头：

```text
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

流式协议：

```text
data: {assistant role chunk}

data: {content delta chunk}
data: {content delta chunk}
...

data: {finish_reason chunk}

data: {usage chunk}      # 仅 include_usage=true 且 Provider usage 完整

data: [DONE]
```

首个 chunk：

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion.chunk",
  "created": 1783751885,
  "model": "mock-stream-model",
  "choices": [
    {
      "index": 0,
      "delta": {
        "role": "assistant"
      },
      "finish_reason": null,
      "logprobs": null
    }
  ]
}
```

内容 chunk：

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion.chunk",
  "created": 1783751885,
  "model": "mock-stream-model",
  "choices": [
    {
      "index": 0,
      "delta": {
        "content": "hello"
      },
      "finish_reason": null,
      "logprobs": null
    }
  ]
}
```

结束 chunk：

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion.chunk",
  "created": 1783751885,
  "model": "mock-stream-model",
  "choices": [
    {
      "index": 0,
      "delta": {},
      "finish_reason": "stop",
      "logprobs": null
    }
  ]
}
```

### Optional usage chunk

请求：

```json
{
  "stream": true,
  "stream_options": {
    "include_usage": true
  }
}
```

Provider 返回完整 usage 时，在 `[DONE]` 前输出：

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion.chunk",
  "created": 1783751885,
  "model": "actual-stream-model",
  "choices": [],
  "usage": {
    "prompt_tokens": 8,
    "completion_tokens": 3,
    "total_tokens": 11
  }
}
```

不完整 usage 不会使用零值补齐，也不会输出 usage chunk。

### Provider routing

标准客户端只传 `model` 时使用：

```text
OPENAI_COMPAT_DEFAULT_PROVIDER
```

默认：

```text
mock
```

网关调用方可以传扩展字段：

```json
{
  "provider": "ollama",
  "model": "qwen2.5:7b",
  "messages": [
    {
      "role": "user",
      "content": "hello"
    }
  ]
}
```

官方 Python SDK 可通过：

```python
extra_body={"provider": "mock"}
```

传递该扩展字段。

### Official Python SDK compatibility

非流式：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="local-test-key",
)

completion = client.chat.completions.create(
    model="mock-compatible-model",
    messages=[
        {
            "role": "user",
            "content": "hello from openai sdk",
        }
    ],
)
```

流式：

```python
stream = client.chat.completions.create(
    model="mock-stream-model",
    messages=[
        {
            "role": "user",
            "content": "hello from sdk stream",
        }
    ],
    stream=True,
    extra_body={
        "provider": "mock",
    },
)

parts = []

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        parts.append(chunk.choices[0].delta.content)

print("".join(parts))
```

Chat-Day4 实测输出：

```text
[mock-stream] [mock] you said: hello from sdk stream
```

`local-test-key` 当前只满足 SDK 初始化；网关 API Key 鉴权安排在 Chat-Day9。

### Streaming error contract

SSE 通道建立后不能再切换为 HTTP 502，因此 Provider 失败时输出可解析的 data-only error：

```text
data: {"error":{"message":"...","type":"api_error","param":null,"code":"provider_error"}}

```

失败流：

```text
不输出 finish chunk
不输出 usage chunk
不输出 data: [DONE]
```

正常流只使用：

```text
data: ...
```

不会泄漏旧接口的：

```text
event: meta
event: token
event: usage
event: done
event: error
```

---

## Conversation Persistence Foundation (Chat-Day5)

Chat-Day5 新增关系数据库持久化基础，但尚未把历史消息自动接入聊天路由。

### Storage strategy

```text
ORM: SQLAlchemy 2.x
Local development: SQLite
Default URL: sqlite:///./data/chat_api.db
Future production: PostgreSQL
```

未来切换 PostgreSQL 时，主要通过 `DATABASE_URL` 替换连接地址：

```text
postgresql+psycopg://user:password@host:5432/chat_api
```

Day5 避免使用 SQLite 专属列类型和手写 `sqlite3` SQL，模型仅使用 SQLAlchemy 通用类型与 ORM API。

### Database initialization

```bash
python -m src.app.db
```

预期：

```text
database initialized: sqlite:///./data/chat_api.db
```

默认创建：

```text
conversations
messages
```

本地数据库目录：

```text
data/
```

已加入 `.gitignore`，不会提交运行时数据库文件。

### Conversation model

```text
id: UUID string
title: nullable string
created_at: UTC datetime
updated_at: UTC datetime
```

### Message model

```text
id: UUID string
conversation_id: foreign key
role: developer/system/user/assistant
content: text
provider: nullable string
model: nullable string
token_count: nullable integer
created_at: UTC datetime
```

外键规则：

```text
Conversation delete
  → Message ON DELETE CASCADE
```

单条 Message 只保存消息级 `token_count`。请求级：

```text
prompt_tokens
completion_tokens
total_tokens
estimated_cost
latency_ms
trace_id
```

暂不放入 Message 表，后续由独立 usage/request 记录承载。

### Architecture

```text
ORM model
  → Repository
  → Service
  → Future API route
```

职责：

```text
Model:
  表结构和 relationship。

Repository:
  add / flush / query / delete；
  不负责 commit。

Service:
  参数规范化；
  Conversation 存在性检查；
  跨 repository 编排；
  commit / rollback。

API route:
  Chat-Day5 未接入数据库。
```

关键模块：

```text
src/app/db/base.py
src/app/db/session.py
src/app/db/types.py
src/app/db/utils.py
src/app/db/models/
src/app/db/repositories/
src/app/services/conversation_service.py
tests/db/
```

### Session boundary

默认 engine 和 session factory 使用懒加载，导入数据库模块不会立即创建本地文件。

SQLite 专属连接配置只在 SQLite backend 生效：

```text
check_same_thread=False
PRAGMA foreign_keys=ON
```

PostgreSQL 不会收到这些连接参数。

### UTC time boundary

新增 `UTCDateTime`：

```text
SQLite:
  bind 时存 UTC naive；
  load 时恢复 UTC-aware。

PostgreSQL:
  使用 timezone-aware DateTime。
```

应用层始终使用 UTC-aware datetime。

### Isolated tests

每个数据库测试使用：

```text
tmp_path/chat_api_test.db
```

因此不会污染：

```text
data/chat_api.db
kb/chroma/chroma.sqlite3
```

### Day5 boundaries

Chat-Day5 未修改：

```text
/chat
/chat/stream
/v1/chat/completions
/prompt/compare
RAG
PromptHub
Replay
Provider implementations
```

也未提前实现：

```text
自动保存聊天消息
自动加载历史
上下文窗口截断
token budget
Conversation HTTP API
usage/cost 落库
```

这些属于 Chat-Day6 及后续阶段。

---


## Multi-Conversation History and Context Window (Chat-Day6)

Chat-Day6 将 Chat-Day5 的数据库基础正式接入项目原生聊天主链路：

```text
POST /chat
POST /chat/stream
```

OpenAI-compatible：

```text
POST /v1/chat/completions
```

继续保持独立、无状态，不自动读取或写入 Conversation 历史。

### Stateful vs stateless boundary

`conversation_id` 是可选字段：

```text
不传 conversation_id:
  继续使用原有无状态行为；
  不读取数据库；
  不写入 Conversation / Message。

传入 conversation_id:
  Conversation 必须已经存在；
  服务端读取历史；
  将截断后的历史与当前 body.messages 合并；
  Provider 完整成功后原子保存当前请求消息和最终 assistant 回复。
```

新 Conversation 通过 `POST /conversations` 创建；聊天接口不会隐式创建 Conversation。

`body.messages` 在有 `conversation_id` 时仍表示“本次新增消息”，不是客户端重复提交的完整历史。

### Message ordering

Message 新增：

```text
sequence_no: integer, >= 1
```

约束：

```text
UNIQUE(conversation_id, sequence_no)
```

历史查询固定按：

```text
sequence_no ASC
```

排序，不依赖 `created_at` 或 UUID，避免相同时间戳与随机 ID 造成顺序漂移。

### Context window

服务端消息合并顺序：

```text
PromptHub / RAG 生成的 server system prompt
→ 截断后的持久化历史
→ 当前 body.messages
```

当前配置：

```text
CONVERSATION_HISTORY_MAX_TURNS=10
CONVERSATION_CONTEXT_TOKEN_BUDGET=4096
CONVERSATION_HISTORY_FETCH_LIMIT=500
```

估算规则：

```text
message_tokens = max(1, ceil(len(content) / 2)) + 4
```

截断原则：

```text
1. 当前请求消息永不删除。
2. system prompt 计入预算。
3. 历史从旧到新淘汰。
4. 优先保留最近完整 user-led turns。
5. 不为了塞入预算而保留半个历史对话轮。
```

### Persistence semantics

同步 `/chat`：

```text
读取历史时使用短 Session
→ Provider 调用期间不持有 DB Session
→ Provider 成功
→ 当前请求消息 + assistant 最终回复在一个事务内提交
```

流式 `/chat/stream`：

```text
先输出 meta / token*
→ 内存累积完整 assistant 内容
→ Provider 正常结束
→ 原子保存当前请求消息 + 完整 assistant
→ 仅在提交成功后输出 usage / done
```

失败语义：

```text
Conversation 不存在:
  在 Provider 调用前返回 HTTP 404。

同步 Provider 失败:
  HTTP 502；
  不保存当前 user；
  不保存 assistant。

流式 Provider 失败:
  event: meta → event: error；
  不输出 usage / done；
  不保存当前 user；
  不保存部分 assistant。

客户端断开:
  传播 asyncio.CancelledError；
  关闭 Provider async iterator；
  不保存部分 assistant。
```

PromptHub / RAG 注入的 server system prompt 只参与当前 Provider 请求，不写入 Message 表。

### Conversation HTTP API

```text
POST   /conversations
GET    /conversations
GET    /conversations/{conversation_id}
PATCH  /conversations/{conversation_id}
DELETE /conversations/{conversation_id}
GET    /conversations/{conversation_id}/messages
```

创建 Conversation：

```bash
curl -s -X POST http://127.0.0.1:8000/conversations \
  -H "Content-Type: application/json" \
  -d '{"title":"My conversation"}' \
  | python -m json.tool
```

Stateful sync chat：

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "mock",
    "model": "mock-model",
    "conversation_id": "<conversation-id>",
    "messages": [
      {
        "role": "user",
        "content": "hello with persisted history"
      }
    ]
  }' | python -m json.tool
```

Stateful stream：

```bash
curl -sN -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "mock",
    "model": "mock-stream-model",
    "conversation_id": "<conversation-id>",
    "messages": [
      {
        "role": "user",
        "content": "continue this conversation"
      }
    ]
  }'
```

查询消息：

```bash
curl -s \
  "http://127.0.0.1:8000/conversations/<conversation-id>/messages?limit=50&offset=0" \
  | python -m json.tool
```

### Compatibility

保持不变：

```text
无 conversation_id 的 /chat 行为
无 conversation_id 的 /chat/stream 事件顺序
PromptHub / RAG / Replay
/prompt/compare
OpenAI-compatible /v1/chat/completions
OpenAI SDK 非流式与 stream=True
```

Day6 commit：

```text
d60c5e3 feat(day6): add conversation history and context window
```

GitHub Actions：

```text
workflow: CI
run id: 29145652536
branch: v2-langchain-rag-plus
sha: d60c5e3
status: completed
result: success
event: push
```

---

## API: Sync Chat

### Sync chat (mock)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"provider":"mock","model":"mock-request-model","messages":[{"role":"user","content":"hi"}]}' | cat
```

Example response（稳定契约字段）：

```json
{
  "trace_id": "...",
  "session_id": null,
  "conversation_id": null,
  "answer": "...",
  "metadata": {
    "provider": "mock",
    "model": "mock-request-model",
    "latency_ms": 0
  }
}
```

### Sync chat (ollama)

确保 Windows 侧有模型：

```powershell
ollama pull qwen2.5:7b
```

调用：

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"provider":"ollama","model":"qwen2.5:7b","messages":[{"role":"user","content":"一句话解释RAG"}],"max_tokens":128}' | cat
```

### Sync chat (OpenAI / OpenAI-compatible)

安装可选依赖并设置配置：

```bash
python -m pip install -r requirements-openai.txt
export OPENAI_API_KEY="..."
export OPENAI_MODEL="your-model-name"
# 可选：export OPENAI_BASE_URL="https://your-compatible-endpoint/v1"
```

调用：

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"provider":"openai","model":"your-model-name","messages":[{"role":"user","content":"Hello"}],"max_tokens":128}' | cat
```

没有配置 `OPENAI_API_KEY` 时，请求会进入 OpenAIProvider，并通过现有同步错误契约返回 HTTP 502，而不是在 schema 层返回 422。

---

## API: Streaming (SSE)

`POST /chat/stream` 返回 **SSE (Server-Sent Events)**，响应头：

* `Content-Type: text/event-stream`

### Event types

* `meta`  : 初始化信息（至少 `trace_id/provider/model`）
* `token` : 增量输出 token/chunk
* `usage` : 统计信息（`trace_id/provider/model/latency_ms/token_events`）
* `done`  : 流式结束（`[DONE]`）
* `error` : 结构化错误（`trace_id/provider/model/latency_ms/error`）

### Example

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"provider":"ollama","messages":[{"role":"user","content":"一句话解释RAG"}],"max_tokens":128}'
```

---

## Error Handling Contract

### Sync `/chat` error contract (HTTP 502)

同步接口下游失败用 **HTTP 502 Bad Gateway** 表达，并在 body 的 `detail` 中返回可机器解析的结构化错误。

示例（强制下游失败）：

```bash
# 注意：必须影响“服务进程”（见下方备注）
export OLLAMA_BASE_URL=http://127.0.0.1:1

curl -i -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"provider":"ollama","messages":[{"role":"user","content":"hi"}]}'
```

示例响应：

```json
{
  "detail": {
    "trace_id": "f519bbe1-550c-41f3-a3ac-957a1e6dd94e",
    "provider": "ollama",
    "model": "qwen2.5:7b",
    "latency_ms": 15,
    "error": "ollama failed: [Errno 111] Connection refused"
  }
}
```

### Streaming `/chat/stream` error contract (SSE `event:error`)

流式接口通常会先建立 SSE 通道（HTTP 200），**业务失败通过 `event:error` 传递**。

示例（强制下游失败）：

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:1

curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"provider":"ollama","messages":[{"role":"user","content":"hi"}],"max_tokens":8}'
```

示例输出：

```text
event: meta
data: {"trace_id":"293e7c41-80a4-4c96-9d10-e9c22129b8bb","provider":"ollama","model":"qwen2.5:7b"}

event: error
data: {"trace_id":"293e7c41-80a4-4c96-9d10-e9c22129b8bb","provider":"ollama","model":"qwen2.5:7b","latency_ms":8,"error":"ollama failed: All connection attempts failed"}
```

### Model field guarantee

为了让前端更省事、契约更硬：`model` **始终是字符串**（不会是 null）：

* 真实 provider：实际模型名（如 `qwen2.5:7b`）
* 未知/缺失：`"unknown"`

适用范围：

* `/chat` 的 `metadata.model`
* `/chat/stream` 的 `meta / usage / error` 事件

---

## SSE event format（补充说明）

每个 SSE “事件块”都遵循以下格式，并以**空行结束**：

```text
event: <type>
data: <string-or-json>

```

说明：

* `data:` 必须是字符串；如果你传的是 dict/list，会先做 JSON 序列化再输出
* `data` 支持多行（会拆成多条 `data:` 行），但同一个事件块仍以空行结束

---

## Runtime debugging（运行时调试）

### 1) 看日志（推荐关注这些字段）

每条请求相关日志建议至少包含：

* `trace_id`
* `provider`
* `model`
* `latency_ms`

当你排障时：

* 先用响应头/响应体拿到 `trace_id`
* 再用 `trace_id` 在日志里定位整条链路

### 2) 常见坑：修改 env 后需要重启服务

`export OLLAMA_BASE_URL=...` 只会影响**当前 shell 启动的进程**。
如果 uvicorn 已经在另一个终端运行，你在新终端里 `export` 不会影响正在跑的服务。

正确做法：

* 在**启动 uvicorn 的那个终端**里 export，再重启服务；或
* 停掉 uvicorn（Ctrl+C）后，在同一终端 export，再启动

---

## Tests

```bash
pytest -q
# 126 passed (Chat-Day6)
```

Chat-Day2：

```text
tests/providers/
tests/chat/test_chat_provider_compatibility.py
tests/stream/test_stream_provider_compatibility.py
tests/prompt/test_prompt_compare_provider_compatibility.py
```

Chat-Day3 / Day4：

```text
tests/openai_compat/test_chat_completions.py
tests/openai_compat/test_chat_completions_stream.py
```

Chat-Day5：

```text
tests/db/conftest.py
tests/db/test_session.py
tests/db/test_conversation_repository.py
tests/db/test_message_repository.py
tests/db/test_conversation_service.py
```

Chat-Day6：

```text
tests/conversations/conftest.py
tests/conversations/test_context_window.py
tests/conversations/test_conversation_api.py
tests/chat/test_chat_conversation_history.py
tests/stream/test_stream_conversation_history.py
```

Chat-Day6 验收：

```text
pytest tests/chat -q
14 passed

pytest tests/conversations -q
7 passed

pytest tests/db -q
14 passed

pytest tests/stream -q
16 passed

pytest tests/openai_compat -q
12 passed

pytest -q
126 passed in 8.17s

GitHub Actions CI
success
```

Day6 测试锁定：

```text
conversation_id 可选边界
无状态请求不访问数据库
Conversation CRUD 与消息分页查询
sequence_no 连续、唯一和稳定排序
历史 + 当前请求的 Provider message 顺序
最近 N 轮与 token budget 截断
同步成功原子保存 user / assistant
流式成功在 usage / done 前保存
PromptHub / RAG server system prompt 不落库
不存在 Conversation 在 Provider 前返回 404
同步 Provider 失败不落库
流式 Provider 失败不落库且无 usage / done
客户端断开不保存部分 assistant
OpenAI-compatible 与旧 SSE 契约无回归
```

---


---

## CI (Day23)

Day23 新增 GitHub Actions：

- workflow: `.github/workflows/ci.yml`
- trigger: push to all branches / pull_request to `master`
- Python: 3.10
- command: `pytest -q`
- embedding: `EMBEDDING_PROVIDER=mock`

CI 使用 `requirements.txt` 安装基础服务与测试依赖：

```bash
python -m pip install -r requirements.txt
pytest -q
```

### CI dependency note

`sentence-transformers / torch / transformers` 没有放进默认 `requirements.txt`。
原因是 CI 测试使用 `EMBEDDING_PROVIDER=mock`，不需要真实 HF embedding 依赖。

Day23 修复了一个 CI import 问题：

- 问题：`src/app/kb/embeddings.py` 顶层 import `sentence_transformers`，导致 mock embedding 的 CI 也失败。
- 修复：将 `sentence_transformers` 改为 HF provider 内部懒加载。
- 效果：基础 CI 保持轻量，真实 HF embedding 仍可按需启用。

---

## System Design and v2 Documentation

系统设计与 v2 收口文档：

- `docs/system_design.md`
- `docs/v2_demo_guide.md`
- `docs/interview_talk_track.md`

覆盖内容：

- Overall architecture
- `/chat` 同步请求链路
- `/chat/stream` SSE 流式链路
- RAG pipeline：ingest → chunk → embedding → Chroma → candidate_k → rerank → top_k → context → citations
- PromptHub / A/B Compare
- Run log / Replay
- Error handling：sync 502 vs stream `event:error`
- Evaluation and regression gates
- Design trade-offs
- Current boundaries and future work

Day23 完成后，chat-api v1 可以视为阶段性完结：服务可运行、demo 可演示、测试可回归、CI 可验证、系统设计可讲解。

Day30 完成后，chat-api v2 可以视为阶段性完结：RAGBackend、LangChain backend、RAG observability、Hybrid RAG、seed/eval workflow、系统设计、演示手册与面试讲解稿均已收口。

## Troubleshooting

* WSL 访问不到 `127.0.0.1:11434`：使用 `/etc/resolv.conf` 的 nameserver IP 作为 Windows 网关，并设置 `OLLAMA_BASE_URL`
* `/api/tags` 返回 `{"models":[]}`：说明还没 pull 模型（Windows 执行 `ollama pull qwen2.5:7b`）

---

---

## Demo（Streaming SSE）

启动服务后，打开：

- `http://localhost:8000/demo`

功能：
- 选择 provider：`mock`（测试）/ `ollama`（本地模型）
- 输入 prompt，点击 Start 开始流式输出
- 页面展示：meta（trace_id/provider/model）、output（token 拼接）、usage、error、done

实现要点：
- Demo 使用 `fetch(POST /chat/stream)` 并读取 `ReadableStream` 解析 SSE（因为 `EventSource` 仅支持 GET）
- SSE 事件块用 `\n\n` 分隔；每块包含 `event:` 与 `data:` 行


### Stop / Abort（Day12）

Demo 现在支持 **Stop** 按钮中断流式请求（使用 `AbortController` + `fetch(..., { signal })`）：

- 点击 **Stop** 会触发 `controller.abort()`，前端立即停止读取流并恢复按钮状态
- `AbortError` 属于“用户主动取消”，不会显示为业务错误（Error 区不会红）
- Stop 后可以直接再次 Start，开始新一轮流式请求（新的 trace_id）

> 说明：当前后端 `event: usage` 主要包含 `latency_ms` 与 `token_events`；如需 `prompt_tokens/completion_tokens` 可在后端增加真实 token 统计后再展示。



---

## Prompt Compare (Day14)

新增接口：`POST /prompt/compare`
同一输入套用两套 Prompt（A/B），返回并列结果与对比指标，并将两条运行记录写入 run log（JSONL）用于回放。

### Example

```bash
curl -s -X POST http://localhost:8000/prompt/compare   -H "Content-Type: application/json"   -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"解释介绍RAG"}],
    "max_tokens":128,
    "temperature":0.7,
    "top_p":0.9,
    "prompt_a":{"prompt_id":"chat","prompt_version":"v1","prompt_vars":{}},
    "prompt_b":{"prompt_id":"qa_strict","prompt_version":"v1","prompt_vars":{}}
  }' | cat
```

返回结构（关键字段）：
- `compare_group_id`
- `a/b.trace_id`
- `a/b.metadata`（含 `prompt_id/prompt_version/provider/model/latency_ms`）
- `metrics`（`latency_ms_*`、`output_chars_*`）

### Run log (JSONL)

默认日志：`runs/prompt_runs.jsonl`
compare 每次写两条（A/B），字段包含：
- `compare_group_id`、`variant`、`mode=compare`
- `trace_id`、`provider/model`
- `prompt_id/prompt_version`
- `latency_ms`、`prompt_chars`、`output_chars`
- `temperature/top_p/max_tokens`

### Replay (offline)

脚本：`scripts/replay_compare.py`

```bash
python scripts/replay_compare.py <compare_group_id>
# 或覆盖日志路径
python scripts/replay_compare.py <compare_group_id> --log ./runs/prompt_runs.jsonl
```

---

## Demo（Stream / Compare）

打开：
- `http://localhost:8000/demo`

支持两种模式：
- **Stream Chat（SSE）**：调用 `/chat/stream`
- **Prompt Compare（A/B）**：调用 `/prompt/compare`

Compare 模式会展示：
- group_id
- A/B 输出并列
- metrics（latency/output diff）
并支持 Copy Curl 复现 compare 请求。

---

## PromptHub Query APIs (Day15)

Day15 将 PromptHub 从“可用”升级为“可查询系统”，新增 3 个接口：

### 1) List prompts

```bash
curl -s http://localhost:8000/prompts | cat
```

返回示例（结构）：

```json
{"prompts":{"chat":["v1","v2"],"qa_strict":["v1"]}}
```

### 2) Replay by trace_id

```bash
curl -s http://localhost:8000/runs/trace/<trace_id> | cat
```

* 找不到：HTTP 404
* 返回包含 `records` 与 `bad_lines`

### 3) Replay compare by compare_group_id

```bash
curl -s http://localhost:8000/runs/compare/<compare_group_id> | cat
```

返回包含：
- `records`（按 A/B 排序）
- `summary`（latency/output diff）
- `bad_lines`

---

### RUN_LOG_PATH（测试/调试）

默认写入：`runs/prompt_runs.jsonl`
你可以通过环境变量覆盖：

```bash
export RUN_LOG_PATH=/tmp/prompt_runs.jsonl
```

注意：环境变量只影响**启动服务的那个进程**；修改后需要重启 uvicorn 才会生效。

---

## Knowledge Base (RAG Day16)

新增 KB 模块，完成 RAG 的“检索最小闭环”（Index + Retrieve）。

### 1) Ingest document

```bash
curl -s -X POST http://localhost:8000/kb/documents \
  -H "Content-Type: application/json" \
  -d '{"title":"t","source":"manual","text":"RAG 是 Retrieval-Augmented Generation，用于检索增强生成。"}' | cat
```

返回包含：`doc_id`、`chunks`、`metadata.trace_id/latency_ms`。

### 2) Search (topK)

```bash
curl -s "http://localhost:8000/kb/search?q=RAG&top_k=3" | cat
```

返回结构（关键字段）：
- `hits[]`: `doc_id/chunk_id/score/text/source/title`
- `metadata.trace_id/latency_ms`

### KB Environment variables

* `KB_DIR` (default: `kb`)
* `KB_CHROMA_DIR` (default: `${KB_DIR}/chroma`)
* `KB_COLLECTION` (default: `kb_chunks`)
* `KB_CHUNK_SIZE` (default: `800`)
* `KB_CHUNK_OVERLAP` (default: `120`)
* `KB_TOP_K` (default: `5`)
* `EMBEDDING_PROVIDER` (default: `mock`, options: `mock|hf`)
* `EMBEDDING_MODEL` (hf provider)
* `EMBEDDING_DIM` (mock provider)

### Notes
- 测试默认使用 `EMBEDDING_PROVIDER=mock`（稳定、无外部下载）。
- 如需真实语义检索演示，可切换为 `EMBEDDING_PROVIDER=hf` 并设置 `EMBEDDING_MODEL`（会下载/加载模型，首次较慢）。

---

## RAG Chat (Day17)

同步 `/chat` 支持检索增强（RAG），通过 KB topK 检索结果注入上下文，并返回结构化 citations。

### Request fields

在 `/chat` 的请求体中新增可选字段：

- `use_kb` (bool, default: false)
- `kb_top_k` (int, optional)

当 `use_kb=true`：
- 先调用 KB 检索（Chroma topK）
- 将 hits 作为 context 注入 system prompt
- 在响应 `metadata.rag` 中返回 `citations`（doc_id/chunk_id/source/title）

### Example

```bash
# 先入库（Day16）
curl -s -X POST http://localhost:8000/kb/documents \
  -H "Content-Type: application/json" \
  -d '{"text":"RAG 是 Retrieval-Augmented Generation，用于检索增强生成。","source":"manual"}' | cat

# 再调用 /chat(use_kb=true)
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"mock",
    "messages":[{"role":"user","content":"什么是RAG？"}],
    "use_kb": true,
    "kb_top_k": 3
  }' | cat
```

响应 `metadata` 中会包含：

- `metadata.rag.enabled`
- `metadata.rag.top_k`
- `metadata.rag.hits`
- `metadata.rag.citations[]`

---

## RAG Streaming (Day18)

`POST /chat/stream` 支持 RAG（检索增强生成）：请求体新增 `use_kb` / `kb_top_k`。当 `use_kb=true` 时：先 KB topK 检索 → 将命中 chunks 作为 context 注入 system prompt → 流式输出答案。

### Stream RAG fields

SSE 事件中会携带 `rag`：
- `meta.data.rag`: `enabled/top_k/hits/context_chars`
- `usage.data.rag`: `enabled/top_k/hits/context_chars/citations/error`
- `error.data.rag`（若下游失败）: `enabled/top_k/hits/context_chars/citations_count/error`

### Example

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"RAG 的最小闭环包括哪些步骤？"}],
    "prompt_id":"chat","prompt_version":"v1",
    "use_kb": true, "kb_top_k": 3,
    "max_tokens": 128
  }'
```

---

## KB Documents Management (Day18)

新增 KB 管理接口：

### 1) List documents

```bash
curl -s "http://localhost:8000/kb/documents?limit=50&offset=0" | cat
curl -s "http://localhost:8000/kb/documents?include_deleted=true" | cat
```

### 2) Delete a document

```bash
curl -s -X DELETE "http://localhost:8000/kb/documents/<doc_id>" | cat
```

删除行为：Chroma 删除（where doc_id）+ 删除 `docs/<doc_id>.md`（若存在）+ `docs.jsonl` 追加 tombstone（deleted=true）。

---

## Demo RAG (Day18)

`/demo` 增强：
- RAG 开关 + top_k 输入框
- 同步/流式均支持 citations 展示
- 修复 SSE 解析（CRLF/data: 兼容 + 只解析完整块）
- Copy Curl 输出 bash 续行 `\`（避免字面量 `\n` 引起 curl 报错）

---

## Tests (Day18)

新增 Day18 契约测试：
- Demo：RAG UI 关键字存在（可演示能力锁死）
- Stream：RAG meta/usage/done 顺序与 rag.citations 结构锁死（含 KB 空降级）
- KB：documents list/delete 行为锁死（含 include_deleted）

当前：

```bash
pytest -q
# 30 passed
```

---

## RAG Evaluation (Day19)

Day19 将 RAG 从“功能可用”推进到“可量化、可回放、可回归”的评测闭环。

### What was added

- `docs/kb_seed/01-11`：项目知识库种子文档。
- `src/app/kb/index_text.py`：统一索引文本抽取，避免 `Keywords/QA Seeds/Appendix/Changelog` 污染向量库。
- `eval/qa_rag_20.jsonl`：20 条 QA 评测集。
- `scripts/eval_qa_rag.py`：离线评测脚本。
- `src/app/kb/rag_context.py`：`build_rag_context()` + query-aware `rerank_hits()`。
- `KB_CANDIDATE_K=50`：先召回候选池，再基于 query/title/text 做轻量 rerank。

### KB Seed structure

每篇 `docs/kb_seed/*.md` 统一结构：

```md
正文（会入库）
---
# Keywords（只给人看，不入库）
# QA Seeds（只给评测/维护，不入库）
```

入库时 `extract_index_text()` 只保留正文。截断规则：

- 优先遇到独立一行 `---` 截断；
- 如果没有 `---`，遇到一级标题 `# Keywords`、`# QA Seeds`、`# Appendix`、`# Changelog` 截断。

### Run evaluation

```bash
python scripts/eval_qa_rag.py \
  --qa eval/qa_rag_20.jsonl \
  --out eval/results/rag_eval_20.jsonl \
  --summary eval/results/rag_eval_20_summary.json \
  --provider ollama
```

输出：

- `eval/results/rag_eval_20.jsonl`：逐题证据，包含 `qid/question/answer/trace_id/rag/citations/answer_score/citation_score/effective_rag/latency_ms`。
- `eval/results/rag_eval_20_summary.json`：汇总指标。

### Metrics

- `answer_hit_rate`：关键词命中，并且回答没有“不确定/需要更多上下文”等拒答模板。
- `citation_hit_rate`：有 citations，且 citation.source 命中 expected_sources。
- `title_hit_rate`：诊断指标，citation.title 是否命中 expected_titles。
- `effective_rag_rate`：`rag.enabled=true && rag.hits>0 && context_chars>0`。
- `avg/p50/p95 latency_ms`：来自 `/chat` 返回的 metadata。

### Final Day19 result

最终 QA20 验收结果：

```text
total = 20
success = 20
failed = 0
answer_hit_rate = 95.0%
citation_hit_rate = 100.0%
effective_rag_rate = 100.0%
avg_latency_ms ≈ 1953ms
```

### Lessons from Day19

Day19 中间经历了多次真实工程问题，并逐个修复：

- 入库 payload 用错字段：`markdown` → `text`，通过 `/openapi.json` 定位 422。
- shell heredoc 管道写错，固定为 `python ... | curl -d @-` 模板。
- 手动删除 `kb/docs/*.md` 造成状态不一致，改为 API tombstone + Chroma delete。
- `Keywords/QA Seeds` 被索引导致召回污染，用 `extract_index_text()` 固化规则。
- md 已更新但 Chroma 仍是旧索引，清理 Chroma 后重新入库验证。
- `candidate_k/rerank/top_k` chunk 原始向量排序靠后，用 `KB_CANDIDATE_K=50` + query-aware rerank 修复。
- rerank 一度过拟合到 `RAG in Chat/Stream`，改为 query 触发的专题 title boost。
- 关键词评测一度误判“不确定回答”为通过，加入 uncertain 拦截。
- “没有找到记录所以 404”一度被 uncertainty pattern 误杀，收窄拒答模板。
- Git 提交时区分源码与运行时产物：不提交 `kb/chroma/`、`kb/docs/`、`kb/docs.jsonl`、`eval/results/`。
- Day19 同时补充了 RAG 评测相关回归点：KB Seed 截断规则、uncertain answer guard、citation/title 命中口径、candidate_k + query-aware rerank，避免 QA Seeds 污染、关键词假阳性和 rerank 全局偏置。

---

## Demo Storyline (Day21)

Day21 不新增后端接口，也不修改核心业务逻辑，而是把已有能力整理成一条 Day22 可演示故事线：

```text
Health
→ PromptHub
→ RAG Sync Chat
→ RAG Streaming SSE
→ Prompt A/B Compare
→ Replay
→ Error Demo
→ Eval Report
```

演示文档：

- `docs/demo_storyline_day22.md`

该文档包含每一步的命令、预期输出和讲解点，方便在面试或复盘时按顺序展示完整 LLM 应用工程闭环。

Day21 不需要新增契约测试，因为没有改变 API contract、schema、RAG 行为或运行时逻辑；仅通过现有回归测试确认系统未受影响：

```bash
pytest -q
# 44 passed
```


## Git hygiene

以下是运行时产物，不建议提交：

```gitignore
kb/chroma/
kb/docs/
kb/docs.jsonl
eval/results/
eval/kb_seed_manifest.jsonl
backup_kb_reset/
```

建议提交：

- `src/**` 源码；
- `docs/kb_seed/*.md` 源文档；
- `eval/qa_rag_20.jsonl` 评测集；
- `scripts/eval_qa_rag.py` 评测脚本；
- README / HANDOFF / day logs。

## RAG Evaluation Report & Regression Gates (Day20)

Day20 将 Day19 的 RAG QA20 离线评测结果整理成 Markdown 报告，并增加回归门槛。

### Generate report

```bash
python scripts/build_eval_report.py \
  --results eval/results/rag_eval_20.jsonl \
  --summary eval/results/rag_eval_20_summary.json \
  --out eval/reports/rag_eval_report.md \
  --strict
```

---

## v1 Closure: CI + System Design (Day23)

Day23 对 chat-api v1 做工程化收口：

- 新增 `requirements.txt`，统一基础依赖安装。
- 新增 `.github/workflows/ci.yml`，push/PR 自动运行 `pytest -q`。
- 修复 CI 中 `sentence-transformers` 顶层 import 导致的 mock 测试失败，改为 HF provider 懒加载。
- 新增 `docs/system_design.md`，将项目从功能列表整理成系统设计说明。
- 最新 GitHub Actions 通过。
- 本地测试保持 `44 passed`。

### v1 accepted capabilities

```text
FastAPI service
mock / ollama provider
sync chat / SSE stream
PromptHub
Prompt A/B Compare
Run log / Replay
KB ingest / search / delete
RAG sync / stream
candidate_k + query-aware rerank
QA20 RAG eval
Markdown report + strict gates
Day22 demo storyline
GitHub Actions CI
System design document
```

Day24 后进入 v2：LangChain backend + Advanced RAG + RAG Eval App。

---

## RAG Backend Skeleton (Day24 / v2)

Day24 是 chat-api v2 的起点，目标不是立即替换现有 RAG 主链路，而是先建立可插拔 RAG backend 架构。

### Branch

```text
v2-langchain-rag
```

### Added files

```text
requirements-langchain.txt
src/app/rag/__init__.py
src/app/rag/base.py
src/app/rag/schemas.py
src/app/rag/native_backend.py
src/app/rag/langchain_backend.py
src/app/rag/factory.py
tests/rag/test_rag_backend_factory.py
```

### RAG_BACKEND

新增环境变量：

```bash
export RAG_BACKEND=native
# or
export RAG_BACKEND=langchain
```

当前行为：

- `native`：默认值，封装现有 embedding → Chroma → rerank → context pipeline。
- `langchain`：Day24 只提供 skeleton + optional dependency lazy loading；正式 LangChain retriever 放到 Day26+。

### Why skeleton first?

Day24 没有立刻改 `/chat` 和 `/chat/stream` 主链路，原因是：

- 这两个接口是 v1 最核心稳定链路；
- 直接改动会影响 `metadata.rag` 和 SSE `rag` 契约；
- sync / stream 两套 RAG 分支都需要同步验证；
- QA20 和 report gate 也需要重新确认。

因此 Day24 只收一个稳定目标：

```text
RAG backend abstraction + factory tests + optional LangChain dependency + CI on feature branches
```

### Tests

```bash
pytest tests/rag/test_rag_backend_factory.py -q
# 3 passed

pytest -q
# 47 passed
```

### CI

Day24 将 CI 触发范围从只跑 `master` 扩展为所有分支 push 都跑：

```yaml
on:
  push:
    branches: ["**"]
  pull_request:
    branches: [ master ]
```

`v2-langchain-rag` 分支 GitHub Actions 已通过。

### Day25 / Day26 completed

Day25 已把 `routes_chat.py` 接入 `get_rag_backend().build_context()`，统一 `/chat` 与 `/chat/stream` 的 RAG 构建逻辑，同时保持现有输出契约不变。

Day26 已实现 `RAG_BACKEND=langchain` 的真实检索能力：通过 `langchain_chroma.Chroma` 查询现有 Chroma KB，并复用项目自己的 embedding engine，保证查询向量空间与入库向量空间一致。

---

## RAGBackend Route Integration (Day25 / v2)

Day25 将 Day24 的 RAG backend abstraction 正式接入主聊天链路。

```text
2c672b6 refactor(day25): route chat rag through backend
```

Day25 之后，`/chat` 与 `/chat/stream` 都调用同一个 backend 接口：

```python
rag_backend = get_rag_backend()
rag_result = rag_backend.build_context(query=query, top_k=top_k)
```

route 层只负责把 `RAGContextResult` 转回既有 API/SSE contract。

验证：

```bash
pytest tests/chat/test_chat_rag_contract.py -q
pytest tests/stream/test_stream_rag_contract.py -q
pytest -q
```

---

## LangChain RAG Backend Retrieval (Day26 / v2)

Day26 让 `RAG_BACKEND=langchain` 从 skeleton 变成真正的检索后端。

```text
c172523 feat(day26): implement langchain rag backend retrieval
1e19e3c test(day26): assert langchain rag backend marker
```

实现方式：

```text
get_embedding_engine(settings)
→ ProjectEmbeddings
→ langchain_chroma.Chroma
→ similarity_search_with_score
→ Hit
→ rerank_hits
→ build_rag_context
→ RAGContextResult
```

LangChain backend 仍保持统一输出：

```text
RAGContextResult.extra = {
  "backend": "langchain",
  "vectorstore": "langchain_chroma"
}
```

验证：

```bash
pytest tests/rag/test_langchain_backend_contract.py -q
# 2 passed

RAG_BACKEND=langchain pytest tests/chat/test_chat_rag_contract.py -q
# 2 passed

RAG_BACKEND=langchain pytest tests/stream/test_stream_rag_contract.py -q
# 2 passed

pytest -q
# 49 passed
```

注意：LangChain / Chroma 测试可能修改 `kb/chroma/chroma.sqlite3`，这是运行时产物，不要提交：

```bash
git restore kb/chroma/chroma.sqlite3
```

Day27 已完成 RAG Observability：backend marker + latency breakdown + trace 增强。

---

## RAG Observability (Day27 / v2)

Day27 adds observability to the RAG pipeline without changing request fields.

### Exposed fields

RAG responses now include:

```text
backend
vectorstore
embedding_ms
retrieval_ms
rerank_ms
context_build_ms
total_ms
```

### Where fields appear

`POST /chat` exposes them in:

```text
metadata.rag
```

`POST /chat/stream` exposes them in:

```text
meta.rag
usage.rag
error.rag
```

### Backend extra

Native backend:

```text
extra = {
  "backend": "native",
  "embedding_ms": ...,
  "retrieval_ms": ...,
  "rerank_ms": ...,
  "context_build_ms": ...,
  "total_ms": ...
}
```

LangChain backend:

```text
extra = {
  "backend": "langchain",
  "vectorstore": "langchain_chroma",
  "embedding_ms": ...,
  "retrieval_ms": ...,
  "rerank_ms": ...,
  "context_build_ms": ...,
  "total_ms": ...
}
```

For LangChain backend, embedding is currently included inside `similarity_search_with_score()`, so it is counted in `retrieval_ms`.

### Tests

Day27 adds / updates:

```text
tests/rag/test_native_backend_observability.py
tests/rag/test_langchain_backend_contract.py
tests/rag/test_langchain_route_observability.py
tests/chat/test_chat_rag_contract.py
tests/stream/test_stream_rag_contract.py
```

Local validation when LangChain optional deps are installed:

```bash
pytest -q
# 52 passed
```

CI remains lightweight because LangChain-specific tests are protected with `pytest.importorskip(...)`.

### Runtime artifact

RAG / Chroma tests may modify:

```text
kb/chroma/chroma.sqlite3
```

Do not commit it:

```bash
git restore kb/chroma/chroma.sqlite3
```

---

## Hybrid RAG Fusion Rerank (Day28 / v2)

Day28 upgrades the RAG ranking stage from vector-only rerank to lightweight Hybrid RAG:

```text
vector retrieval
→ lexical scoring
→ fusion rerank
→ top_k context
```

The request contract is unchanged. Existing `/chat` and `/chat/stream` clients do not need to change request fields.

### Fusion signals

Hybrid rerank combines:

```text
1. vector score：semantic retrieval score from Chroma / LangChain Chroma
2. lexical score：query token overlap, title/source/text match, exact phrase bonus
3. query-aware rule bonus：the existing topic-specific rerank rules from Day19/Day20
```

Current fixed weights:

```text
retrieval_mode = "hybrid"
fusion = "vector_lexical"
vector_weight = 0.7
lexical_weight = 0.3
```

### API observability

`POST /chat` exposes Hybrid RAG fields in `metadata.rag`.

`POST /chat/stream` exposes the same fields in `meta.rag` / `usage.rag` / `error.rag`.

Fields:

```text
backend
vectorstore
retrieval_mode
fusion
vector_weight
lexical_weight
embedding_ms
retrieval_ms
rerank_ms
context_build_ms
total_ms
```

### Tests

Day28 adds / updates:

```text
tests/kb/test_hybrid_rag_rerank.py
tests/rag/test_native_backend_observability.py
tests/rag/test_langchain_backend_contract.py
tests/chat/test_chat_rag_contract.py
tests/stream/test_stream_rag_contract.py
tests/rag/test_langchain_route_observability.py
```

Local validation:

```bash
pytest -q
# 57 passed
```

### Day28 QA20 result

After rebuilding live KB from `docs/kb_seed/01-11` and running QA20:

```text
answer_hit_rate = 90.0%
citation_hit_rate = 100.0%
effective_rag_rate = 100.0%
title_hit_rate = 95.0%
avg_latency_ms = 1958
p50_latency_ms = 1706
p95_latency_ms = 5921
failed = 0
```

Strict report gate:

```bash
python scripts/build_eval_report.py \
  --results eval/results/rag_eval_20_day28_hybrid.jsonl \
  --summary eval/results/rag_eval_20_day28_hybrid_summary.json \
  --out eval/reports/rag_eval_report_day28_hybrid.md \
  --strict
# All regression gates passed!
```

### Day28 troubleshooting notes

Day28-C exposed two important evaluation pitfalls:

1. **Live KB state matters.** The first Day28 eval failed because the live KB still contained demo documents, so citations pointed to `source=demo` instead of `docs/kb_seed/*`.
2. **Citation scoring should match evaluation intent.** QA20 uses source categories such as `kb_seed`, while runtime citations contain full paths such as `docs/kb_seed/07_KB Ingest & Search.md`. Day28 fixed `scripts/eval_qa_rag.py` to use normalized substring matching and title/source fallback, instead of brittle exact matching.

### Runtime artifact note

Do not commit runtime KB / eval outputs:

```bash
git restore kb/chroma kb/docs.jsonl kb/docs 2>/dev/null || true
git restore eval/reports/rag_eval_report_day28_hybrid.md 2>/dev/null || true
```

Usually do not commit:

```text
eval/results/rag_eval_20_day28_hybrid.jsonl
eval/results/rag_eval_20_day28_hybrid_summary.json
```

---

## KB Seed and RAG Eval Workflow (Day29 / v2)

Day29 turns the manual Day28-C KB rebuild and QA20 evaluation steps into repeatable scripts.

### Seed KB

Script:

```text
scripts/seed_kb.py
```

Main capabilities:

```text
1. Select docs/kb_seed/01-11 by default
2. Keep source as docs/kb_seed/<filename>.md
3. Extract title from filename
4. Support --dry-run
5. Support --reset-runtime --yes
6. Support --ingest through POST /kb/documents
7. Write eval/kb_seed_manifest.jsonl
```

Dry run:

```bash
python scripts/seed_kb.py --dry-run
```

Reset runtime artifacts. Stop uvicorn before this step:

```bash
python scripts/seed_kb.py --reset-runtime --yes
```

After restarting uvicorn, ingest seed docs:

```bash
python scripts/seed_kb.py --ingest
```

### Run full QA20 workflow

Script:

```text
scripts/run_rag_eval_workflow.py
```

The workflow performs:

```text
health check
→ seed KB
→ provider warmup
→ run eval_qa_rag.py
→ build_eval_report.py --strict
→ print summary
```

Example:

```bash
python scripts/run_rag_eval_workflow.py \
  --provider ollama \
  --results eval/results/rag_eval_20_day29_workflow.jsonl \
  --summary eval/results/rag_eval_20_day29_workflow_summary.json \
  --report eval/reports/rag_eval_report_day29_workflow.md
```

Runtime reset is intentionally separated from eval. Stop uvicorn first:

```bash
python scripts/run_rag_eval_workflow.py --reset-runtime --yes
```

Then restart uvicorn and rerun the workflow without `--reset-runtime`.

### Provider warmup

Day29-C adds provider warmup before formal QA20 evaluation:

```text
POST /chat
provider = ollama
use_kb = false
max_tokens = 16
temperature = 0.0
```

This avoids Ollama cold-start / first-request latency spikes from polluting the 20-sample p95 gate.

You can skip it explicitly:

```bash
python scripts/run_rag_eval_workflow.py --skip-warmup
```

### Day29 final QA20 result

After seed workflow + warmup:

```text
total = 20
success = 20
failed = 0
answer_hit_rate = 90.0%
citation_hit_rate = 100.0%
effective_rag_rate = 100.0%
title_hit_rate = 95.0%
avg_latency_ms = 1495
p50_latency_ms = 1396
p95_latency_ms = 2750
```

Strict report gate:

```text
All regression gates passed!
```

### Day29 tests

Day29 adds:

```text
tests/scripts/test_seed_kb.py
tests/scripts/test_run_rag_eval_workflow.py
```

Validation:

```bash
pytest -q
# 63 passed
```

### Runtime artifact note

Do not commit workflow outputs:

```text
eval/kb_seed_manifest.jsonl
eval/results/
eval/reports/
kb/chroma/
kb/docs/
kb/docs.jsonl
```
---

## v2 Closure (Day30)

Day30 completes the `v2-langchain-rag` phase as a packaged, demonstrable, and interview-ready version.

### What Day30 added

Day30 is documentation and acceptance closure, not a new feature day.

Added / completed docs:

```text
docs/system_design.md
docs/v2_demo_guide.md
docs/interview_talk_track.md
```

### Documentation roles

```text
docs/system_design.md
  系统设计文档：讲架构、模块关系、RAG pipeline、设计取舍、当前边界与未来扩展。

docs/v2_demo_guide.md
  演示手册：按顺序跑 health、sync chat、stream、RAG、Hybrid metadata、Prompt Compare、Replay、eval workflow。

docs/interview_talk_track.md
  面试讲解稿：包含 30 秒 / 1 分钟 / 3 分钟项目介绍、RAG 讲法、真实排障案例、常见问答和简历 bullet。
```

### Final v2 accepted capabilities

```text
FastAPI service
mock / ollama provider
sync /chat
SSE /chat/stream
PromptHub
Prompt A/B Compare
Run Log / Replay
KB ingest / search / delete
RAG sync / stream
candidate_k + query-aware rerank
RAGBackend abstraction
native / langchain backend
RAG observability timing
Hybrid RAG fusion rerank
QA20 RAG eval
Strict regression gates
KB seed workflow
RAG eval workflow
Provider warmup for local Ollama eval
GitHub Actions CI
System design document
Demo guide
Interview talk track
```

### Final validation commands

Run tests:

```bash
pytest -q
# 63 passed
```

Run reproducible local RAG acceptance workflow:

```bash
# Stop uvicorn first
python scripts/run_rag_eval_workflow.py --reset-runtime --yes

# Restart uvicorn
WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"
python -m uvicorn src.app.main:app --reload --port 8000

# In another terminal
python scripts/run_rag_eval_workflow.py --provider ollama
```

Expected strict gate:

```text
answer_hit_rate >= 0.90
citation_hit_rate >= 0.95
effective_rag_rate >= 0.95
title_hit_rate >= 0.85
p95_latency_ms <= 6000
failed_count == 0
```

Latest validated result:

```text
total = 20
success = 20
failed = 0
answer_hit_rate = 0.90
citation_hit_rate = 1.00
effective_rag_rate = 1.00
title_hit_rate = 0.95
avg_latency_ms = 1495
p50_latency_ms = 1396
p95_latency_ms = 2750
All regression gates passed!
```

### v2-plus Current Status (Chat-Day6 completed)

`chat-api v2-langchain-rag` 继续作为 RAG / LangChain / Hybrid RAG / Eval Workflow 项目基线保留；当前开发分支为：

```text
v2-langchain-rag-plus
```

已完成：

```text
Chat-Day2:
  统一 ChatProvider / ProviderFactory；
  Mock / Ollama / OpenAI Provider；
  request-level provider/model override。

Chat-Day3:
  OpenAI-compatible 非流式 chat.completion。

Chat-Day4:
  OpenAI-compatible chat.completion.chunk SSE。

Chat-Day5:
  SQLAlchemy 2.x 持久化基础；
  Conversation / Message ORM；
  SQLite / PostgreSQL boundary；
  repository / service / isolated tests。

Chat-Day6:
  Conversation HTTP API；
  conversation_id 可选边界；
  sequence_no 稳定排序；
  历史加载与 context window；
  同步/流式成功后原子落库；
  Provider 失败与客户端断开不保存半轮消息。
```

当前数据模型：

```text
Conversation:
  id / title / created_at / updated_at

Message:
  id / conversation_id / sequence_no /
  role / content / provider / model /
  token_count / created_at
```

当前原生聊天边界：

```text
/chat 和 /chat/stream:
  不传 conversation_id → 无状态；
  传 conversation_id → 服务端历史 + 持久化。

/v1/chat/completions:
  保持独立 OpenAI-compatible 无状态接口。
```

最终验收：

```text
tests/chat -> 14 passed
tests/conversations -> 7 passed
tests/db -> 14 passed
tests/stream -> 16 passed
tests/openai_compat -> 12 passed
pytest -q -> 126 passed in 8.17s
manual API acceptance -> passed
database sequence check -> unique and continuous
sync provider failure no-write -> passed
stream provider failure no-write -> passed
client disconnect no-write -> deterministic test passed
GitHub Actions CI -> success
commit -> d60c5e3
workflow run -> 29145652536
data/chat_api.db -> ignored runtime artifact
```

下一里程碑：

```text
Chat-Day7: Token usage accounting
```

Day7 应优先明确：

```text
Provider 原生 usage 与本地估算 usage 的区分
同步与流式统一 usage record
request / trace / conversation 关联
prompt_tokens / completion_tokens / total_tokens
失败请求是否记录 usage
避免把请求级 usage 强塞进 Message 表
为 Day8 cost estimation 和 usage summary API 建立数据边界
```
