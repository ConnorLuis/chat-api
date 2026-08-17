# HANDOFF — chat-api v2-plus（Chat-Day11 completed）

> 新对话开场可直接粘贴：`chat-api 当前以 v2-langchain-rag-plus 为目标分支，定位为 production-oriented、单租户的 LLM Chat Gateway。Chat-Day1～Day11 已完成统一 Provider、OpenAI-compatible 同步/流式、Conversation/Message 持久化、上下文窗口、usage/cost、API Key 鉴权、请求限流、每日 token quota，以及 timeout/retry/fallback 与执行链可观测性；Day9B 已完成依赖、CI、配置、运行产物和文档收口。Day11 本地 Python 3.10 严格验收为 286 passed、0 skipped、0 warnings，目标分支远端验收以 Day11 提交对应的 GitHub Actions passed 为准。下一步只做并发压测、Docker 与发布文档，不向 chat-api 增加 Agentic RAG、GraphRAG、Multi-Agent 或 MCP。`

## 1. 当前事实

| 项目 | 当前值 |
|---|---|
| 仓库 | `ConnorLuis/chat-api` |
| 目标分支 | `v2-langchain-rag-plus` |
| Day9B 收口提交 | `09a2222 chore(day9b): close repository and CI hygiene` |
| Python | 3.10.19 |
| 应用框架 | FastAPI + SQLAlchemy 2.x |
| 默认数据库 | `sqlite:///./data/chat_api.db` |
| 默认 Provider | request 决定；测试使用 `mock` |
| 默认 embedding | `mock`，维度 512 |
| 默认 RAG backend | `native` |
| 当前完整测试 | `286 passed, 0 skipped, 0 warnings` |
| Day9B 远端验收 | `v2-langchain-rag-plus` GitHub Actions：passed |
| Day11 本地验收 | Python 3.10：passed |
| Day11 远端验收 | Day11 提交对应的 GitHub Actions 必须 passed |

Day9B 已通过本地与目标分支远端验收。Day11 已通过本地严格验收；目标分支远端结果以本次提交对应的最新 GitHub Actions run 为准。

## 2. 项目定位与边界

`chat-api` 是 LLM Chat Gateway / Chat Backend 工程项目，重点是：

- 多 Provider 统一接入；
- 原生与 OpenAI-compatible API；
- SSE 流式协议；
- Conversation / Message 持久化和上下文窗口；
- usage、cost、鉴权、限流和 token quota；
- RAG backend、评测、可观测性与工程交付。

`agent-api` 负责 Agentic RAG、GraphRAG、Multi-Agent、LangGraph 编排和 MCP。不要在 `chat-api` 重复实现这些能力。

当前不再扩展 Prompt cache、多租户 RBAC、复杂 Agent Graph 等新范围。Provider resilience 已完成，剩余工作只围绕压测、Docker 和最终发布质量。

## 3. 已完成能力

### Chat-Day1～Day6：Gateway 与会话基础

- Mock / Ollama / OpenAI 统一 `ChatProvider` 和 `ProviderFactory`；
- request-level provider/model override；
- 原生 `/chat`、`/chat/stream`；
- OpenAI-compatible `/v1/chat/completions` 同步与流式子集；
- Conversation / Message、Repository / Service、稳定消息顺序；
- 多会话历史、最近 N 轮和 token budget 截断；
- 同步/流式仅在完整成功后保存本轮 user/assistant；
- Provider 失败或客户端断开不保存半轮 assistant。

### Chat-Day7～Day8：usage 与 cost

- `UsageRecord` 保存请求级 token、来源、状态、trace/conversation/provider/model/latency；
- 区分 `provider_native`、`local_estimate` 和 `unavailable`；
- 区分 succeeded、provider_failed、client_disconnected、persistence_failed；
- 版本化 pricing catalog 和 Decimal 固定精度；
- `UsageCost` 保存不可变价格快照；
- 区分 `estimated`、`unknown_price`、`usage_unavailable`；
- `/usage/pricing|records|summary|daily|providers|models` reporting API；
- 不把请求级 usage/cost 写入 `Message`。

### Chat-Day9：API Key authentication

- API Key 明文只在创建时返回一次；
- 数据库仅保存 prefix、HMAC-SHA256 hash 和 metadata；
- server-side pepper 不进入数据库或 Git；
- active/revoked 生命周期和真实 revoke；
- `Authorization: Bearer`、`X-API-Key`、冲突 header 检查；
- `CallerIdentity` 和 `/auth/whoami`；
- native/OpenAI-compatible 错误契约保持隔离；
- `/health`、`/ready`、文档入口等公共路由与受保护业务路由分离。

### Chat-Day10：rate limit 与 token quota

- 用户/API Key 和 IP 维度的请求限制；
- 用户/IP 独立请求数与窗口配置；
- 默认不信任代理转发的客户端 IP header；
- caller-aware 每日 token quota；
- 原生 `/chat` 和 `/chat/stream` quota/usage 结算；
- OpenAI-compatible 同步和流式 usage accounting；
- rate limit 与 token quota 可独立开关，默认均关闭，保持旧接口兼容。

### Chat-Day11：Provider resilience

- 统一错误分类：timeout、connection、rate limit、unavailable、request、dependency、configuration、stream interrupted；
- timeout/connection/HTTP 408/429/5xx 可重试，其余配置、依赖、其他 4xx 和未知错误默认不重试；
- `max_attempts` 包含首次调用，默认 2 次，指数退避默认从 100ms 开始并限制在 1000ms；
- OpenAI SDK 内置 retry 固定为 0，由网关提供唯一重试语义；
- fallback 默认关闭，只在 primary 可重试错误耗尽后触发；
- fallback 使用显式 fallback model 或自身默认模型，不继承 primary request model；
- 流式仅允许在首个非空 token 前 retry/fallback，输出开始后的错误统一为 stream interrupted；
- `/chat`、Prompt Compare、原生 SSE 与 OpenAI-compatible 同步/流式均暴露执行链；
- 成功 usage/cost 归属于最终 Provider/Model，失败尝试保留在 resilience observability 中；
- 没有为了本阶段先拆大路由，避免把行为重构与 resilience 语义混在同一次改动中。

### v2 RAG 能力

- `RAG_BACKEND=native|langchain` 抽象；
- Native 与 LangChain Chroma backend；
- 复用项目 embedding，保证入库和查询向量空间一致；
- vector + lexical fusion rerank；
- citations、backend marker、retrieval/fusion/timing observability；
- KB ingest/search/list/soft-delete；
- QA20、seed、workflow、report 和 strict regression gates。

详细 Day1～Day30 历史过程保留在 README 对应章节、`docs/` 和 Git 历史中；HANDOFF 不再复制整份开发日志。

## 4. 当前关键语义

### Provider 边界

唯一模型调用边界是：

```text
HTTP route / business preparation
  -> ProviderFactory
  -> ResilientChatProvider
     -> primary ChatProvider
     -> optional fallback ChatProvider
        -> MockProvider / OllamaProvider / OpenAIProvider
```

无调用方的旧 `src/app/llm/engines/` 已删除。不要重新引入双层 Engine/Provider 兼容层。

### Native SSE

正常事件顺序：

```text
meta -> token* -> usage -> done
```

Provider 失败：

```text
meta -> token* -> error
```

SSE 响应头已经发送后，业务失败仍是 HTTP 200，通过 `event:error` 表达；失败流不再发送 `usage` 或 `done`。

### Retry / fallback

- 可重试：timeout、connection、HTTP 408/429/5xx；
- 不可重试：dependency/configuration、其他 HTTP 4xx、未知 invocation error；
- fallback 只发生在 primary 可重试错误耗尽后，默认关闭；
- 首个非空 token 是流式不可回退边界；输出开始后不 retry、不 fallback；
- `PROVIDER_FALLBACK_MODEL` 与 primary 请求模型解耦；
- `ProviderExecutionMetadata` 记录 primary/final Provider、总尝试数、retry 次数、fallback 状态和每次尝试结果。

公开字段：

```text
/chat、/prompt/compare -> metadata.provider_execution
/chat/stream -> usage/error.provider_execution
OpenAI sync -> gateway.provider_execution
OpenAI stream -> finish chunk 或 error event 的 gateway.provider_execution
```

成功时 accounting 使用最终 Provider/Model；fallback 之前的失败尝试不会生成额外 UsageRecord 或重复计费。

### Persistence

- route 进入 Provider 前只短暂读取历史；
- 网络调用期间不持有数据库 session；
- 同步成功后原子保存本轮消息和请求 accounting；
- 流式成功在完成语义成立后保存；
- Provider 失败、断流和客户端断开不写半轮 assistant；
- OpenAI-compatible endpoint 保持其独立协议边界，不复用原生响应 envelope。

### Usage / cost

- `UsageRecord` 是请求级事实；
- `UsageCost` 是对应请求的价格快照；
- `Message` 只保存对话消息；
- unknown price 或 usage unavailable 时不伪造金额；
- 不用当前价格重算历史记录。

### Auth / limiter / quota

- 鉴权、请求限流和 token quota 是三个独立边界；
- `API_AUTH_ENABLED=false` 时保持迁移兼容；
- `RATE_LIMIT_TRUST_PROXY_HEADERS=false` 是安全默认值；
- 多 worker / 多实例下的分布式计数属于 Redis 等外部存储边界，当前项目不要声称已经解决该问题。

## 5. 配置与依赖

### 依赖文件

| 文件 | 用途 |
|---|---|
| `constraints.txt` | 固定直接依赖与兼容性关键依赖版本 |
| `requirements.txt` | 核心运行依赖 |
| `requirements-dev.txt` | pytest、Starlette TestClient 所需 `httpx2` |
| `requirements-langchain.txt` | `langchain-core`、`langchain-chroma` |
| `requirements-openai.txt` | OpenAI SDK |
| `requirements-embeddings.txt` | 真实 Sentence Transformers embedding，可选且不进入 CI |

项目没有直接使用高层 `langchain` 或 `langchain-ollama` 包。

### 环境变量

以 `.env.example` 为完整模板。应用读取进程环境变量，不会自动加载 `.env`：

```bash
cp .env.example .env
set -a && source .env && set +a
```

关键默认值：

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
PROVIDER_RETRY_MAX_ATTEMPTS=2
PROVIDER_RETRY_BASE_DELAY_MS=100
PROVIDER_RETRY_MAX_DELAY_MS=1000
PROVIDER_FALLBACK_ENABLED=false
PROVIDER_FALLBACK_PROVIDER=
PROVIDER_FALLBACK_MODEL=
DATABASE_URL=sqlite:///./data/chat_api.db
API_AUTH_ENABLED=false
REQUEST_RATE_LIMIT_ENABLED=false
RATE_LIMIT_TRUST_PROXY_HEADERS=false
TOKEN_QUOTA_ENABLED=false
DAILY_TOKEN_QUOTA_TOKENS=100000
CONVERSATION_CONTEXT_TOKEN_BUDGET=4096
KB_TOP_K=3
RAG_BACKEND=native
EMBEDDING_PROVIDER=mock
EMBEDDING_MODEL=maidalun1020/bce-embedding-base_v1
EMBEDDING_DIM=512
```

WSL 访问 Windows Ollama 时，使用 Windows 网关地址：

```bash
WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"
```

## 6. Chat-Day9B 收口内容

### 依赖与 CI

- 添加 exact constraints；
- pytest 从运行依赖移入开发依赖；
- 添加 `httpx2`，消除 Starlette TestClient 弃用 warning；
- CI 使用 `actions/checkout@v5`、`actions/setup-python@v6`；
- push / pull request 对所有分支触发；
- CI 安装 dev、LangChain、OpenAI requirements；
- CI 执行 `pip check`、warnings-as-errors compile 和全量 pytest。

### skip 与 warning

- 完整环境安装 LangChain 依赖，原来的两个 module-level skip 被消除；
- core-only 环境仍通过 `pytest.importorskip` 跳过，但带有明确安装原因；
- `pytest.ini` 使用 `-ra --strict-config --strict-markers` 和 `filterwarnings=error`；
- 修复 SSE 非法转义；
- 修复 Python 3.12 对 `datetime.utcnow()` 的弃用 warning，时间改为 timezone-aware UTC。

### 配置与代码

- Ollama 默认地址从错误的 `127.0.0.1:9999` 改为标准 `127.0.0.1:11434`；
- embedding 默认值从个人机器路径改为 `maidalun1020/bce-embedding-base_v1`；
- 修复 `HFEmbeddingEngine.__init__` 缩进/初始化问题；
- 添加 settings 和 HF embedding contract tests；
- 删除无引用的 `src/app/llm/engines/`。

### Repository hygiene

- `.env.example` 可提交，`.env` 和 `.env.*` 不提交；
- `data/`、`runs/`、数据库、日志、Chroma 和生成 KB 文档不提交；
- Chroma/KB 运行文件已经从 Git index 移除，但本机文件保留；
- `docs/kb_seed/` 是源文档，仍应提交；
- eval 生成结果和临时备份不提交。

## 7. 验收命令与结果

创建独立环境：

```bash
python -m venv .venv-day11
.venv-day11/bin/python -m pip install --upgrade pip
.venv-day11/bin/python -m pip install \
  -r requirements-dev.txt \
  -r requirements-langchain.txt \
  -r requirements-openai.txt
```

严格验收：

```bash
.venv-day11/bin/python -m pip check
.venv-day11/bin/python -W error -m compileall -q src tests
EMBEDDING_PROVIDER=mock \
API_AUTH_ENABLED=false \
REQUEST_RATE_LIMIT_ENABLED=false \
TOKEN_QUOTA_ENABLED=false \
.venv-day11/bin/python -m pytest -q
git diff --check
```

本地结果：

```text
Python 3.10.19
pip check -> No broken requirements found
compileall src/tests warnings-as-errors -> passed
pytest -> 286 passed in 18.44s
skipped -> 0
warnings -> 0
git diff --check -> passed
```

Day9B 目标分支远端验收已通过。Day11 目标分支远端验收需在本次提交推送后，以对应 GitHub Actions run 为最终结果。

## 8. Git 提交边界

应该提交：

- `src/**`、`tests/**`、`scripts/**`；
- `.github/workflows/ci.yml`；
- `.gitignore`、`.env.example`、`pytest.ini`；
- requirements / constraints；
- README、HANDOFF 和正式设计文档；
- `docs/kb_seed/**` 源文档。

不应提交：

- `.env`、API Key、pepper；
- `data/**`、`runs/**`、`*.db`、`*.sqlite3`、`*.log`；
- `kb/chroma/**`、`kb/docs/**`、`kb/docs.jsonl`；
- eval 输出、临时 patch、备份和本地路线图。

提交前检查：

```bash
git diff --check
git ls-files 'kb/chroma/**' 'kb/docs/**' 'kb/docs.jsonl' 'data/**'
rg -n 'src\.app\.llm\.engines|app\.llm\.engines' src tests scripts
git status --short
```

第二、三条应无输出。

## 9. 已知未完成项

Provider resilience 已完成，当前剩余项：

1. 并发压测，以及吞吐量、P50/P95、错误率和测试环境记录；
2. Dockerfile、docker-compose 和最终一键启动；
3. 最终发布 README、演示命令与面试数据整理。

Alembic/PostgreSQL、多实例分布式 limiter/quota 和完整 metrics/tracing backend 属于未来演进边界，不作为本轮 chat-api 简历项目收口的必做项。大路由拆分也不是 Day11 遗留缺陷；只有后续改动确实受阻时，才允许做保持行为不变的独立重构。

## 10. 下一步顺序

### Chat-Day12：并发压测

- 固定 Python、硬件、Provider、模型和请求 payload；
- 至少覆盖 Mock 基准与一个真实 Provider 场景；
- 分档记录并发数、请求总数、吞吐量、P50/P95、错误率；
- 区分同步与流式首 token/完整响应延迟；
- 输出可复现命令和结果文件，不把本机偶然结果写成通用性能承诺。

### Chat-Day13：Docker 与发布收口

- Dockerfile、docker-compose 和健康检查；
- 一键启动、环境变量、持久化卷与 Ollama 连接说明；
- 最终 README、演示脚本和面试讲解口径；
- 完整本地验收与目标分支 GitHub Actions。

## 11. 关键提交

```text
d60c5e3 feat(day6): conversation history and context window
bab036c feat(day7): add token usage accounting
22bd6c9 feat(day8): add cost estimation and usage reporting
7769b78 feat(day9): add API key authentication
7f22eff docs(day9): update authentication documentation
34f9b2e feat(day10): add request rate limiting
0c731fe feat(day10): add caller-aware daily token quota
c21ef6b feat(day10): enforce native chat token quota
cf21b13 feat(day10): account OpenAI-compatible sync usage
e8e0ab3 feat(day10): account OpenAI-compatible streaming usage
09a2222 chore(day9b): close repository and CI hygiene
5b09bd8 docs(day9b): record final remote acceptance
```

Day9B cleanup implementation commit：`09a2222 chore(day9b): close repository and CI hygiene`。

Day11 代码、测试和本文档应合并为一个提交，建议标题：`feat(day11): add provider resilience and observability`。推送后再记录该提交对应的 GitHub Actions run，不需要为 hash 反复修改同一提交。
