# HANDOFF — chat-api v2-plus（Chat-Day13 completed / v2-plus closed）

> 新对话开场可直接粘贴：`chat-api 的 v2-langchain-rag-plus 已正式收口，定位为 production-oriented、单租户的 LLM Chat Gateway。Chat-Day1～Day13 已完成多 Provider、OpenAI-compatible 同步/流式、会话持久化、usage/cost、鉴权限流、Provider resilience、可复现压测，以及固定 Python 3.10 的非 root Docker 发布单元。Day13 实现提交 5c75a35 已通过目标 WSL 本地验收和 GitHub Actions run 32107582238；远端 Python 全量测试为 322 passed，Docker 容器 healthy，六链路 smoke 全部通过。chat-api 后续只做复习、演示和必要维护，不增加 Agentic RAG、GraphRAG、Multi-Agent 或 MCP。`

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
| Day11 Python 3.10 基线 | `286 passed, 0 skipped, 0 warnings` |
| Day9B 远端验收 | `v2-langchain-rag-plus` GitHub Actions：passed |
| Day11 本地验收 | Python 3.10：passed |
| Day11 收口提交 | `39ad9d4 feat(day11): add provider resilience and observability` |
| Day11 远端验收 | GitHub Actions run `32028750201`：passed |
| Day12 Python 3.10 本地验收 | `303 passed in 18.38s`，compile/diff check passed |
| Day12 实现提交 | `a23c92e feat(day12): add reproducible load testing` |
| Day12 远端验收 | GitHub Actions run `32032592555`：passed |
| Day12 最终文档提交 | `ff47733 docs(day12): record mock load-test baseline` |
| Day12 最终 CI | GitHub Actions run `32034762231`：passed |
| Day12 实测 | clean commit 上连续 3 次、8 场景、共 3,960 个测量请求 |
| Day12 当前状态 | completed；mock baseline 已复核并记录 |
| Day13 实现提交 | `5c75a35 chore(day13): add docker release packaging` |
| Day13 辅助开发验收 | Python 3.12：`322 passed`；真实 Uvicorn 六链路 smoke passed |
| Day13 目标环境验收 | Python 3.10.19：`322 passed in 18.24s`；Docker build/health/volumes/smoke/Ollama passed |
| Day13 远端验收 | GitHub Actions run `32107582238`：Python job `95620047535` 与 Docker job `95620047554` 均 passed |
| Day13 远端测试 | Python 3.10：`322 passed in 17.65s`；Docker healthy；协议 smoke 6/6 passed |
| Day13 当前状态 | completed；`chat-api` v2-plus closed |

Day9B、Day11、Day12 与 Day13 均已通过各自本地严格验收和目标分支 GitHub Actions。Day13 的实现提交与两个远端 job 已全部通过，`chat-api` v2-plus 发布收口完成。

## 2. 项目定位与边界

`chat-api` 是 LLM Chat Gateway / Chat Backend 工程项目，重点是：

- 多 Provider 统一接入；
- 原生与 OpenAI-compatible API；
- SSE 流式协议；
- Conversation / Message 持久化和上下文窗口；
- usage、cost、鉴权、限流和 token quota；
- RAG backend、评测、可观测性与工程交付。

`agent-api` 负责 Agentic RAG、GraphRAG、Multi-Agent、LangGraph 编排和 MCP。不要在 `chat-api` 重复实现这些能力。

当前不再扩展 Prompt cache、多租户 RBAC、复杂 Agent Graph 等新范围。`chat-api` 功能开发已经收口，后续只允许必要维护、面试复习和可复现演示，不再增加业务能力。

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

### Chat-Day12：可复现并发压测（completed）

- `scripts/load_test.py`：异步 worker 并发、warm-up、原生/OpenAI-compatible 同步与流式协议校验；
- `scripts/run_load_test.py`：配置驱动 CLI，自动完成 preflight、逐场景运行和结果落盘；
- `benchmarks/configs/mock_baseline.json`：Mock 的 c1/c10/c25/c50 固定场景矩阵；
- `benchmarks/configs/ollama_baseline.example.json`：真实模型端到端示例，不把特定机器数字当作通用性能；
- `report.md` 汇总 req/s、P50/P95/P99、错误率和 TTFT；场景 JSON 保留逐请求样本；
- HTTP 2xx 但 JSON 契约错误、SSE error 或缺失终止事件均计为失败；
- API Key 只从环境读取，结果只记录是否配置，绝不写入明文；
- `APP_LOG_LEVEL=WARNING` 可关闭应用逐请求 INFO 日志，避免终端输出污染正式基准；
- `benchmarks/results/` 是被 Git 忽略的运行产物。
- 实现提交 `a23c92e` 已通过 GitHub Actions run `32032592555`；
- 在该 clean commit 上连续完成三次 mock suite，共 3,960 个测量请求，整体错误率 49/3,960（1.237%）；
- 除 `native-sync-c50` 外七个场景三次均为 0 错误；C50 合计 49/1,500（3.267%）失败；
- 49 个失败全部是持久化阶段 SQLAlchemy QueuePool 耗尽导致的 HTTP 500，未混入 Provider/协议类错误；
- 三次聚合表和性能边界解释已写入 README 的 `Mock baseline` 小节。

### Chat-Day13：Docker 与发布收口（completed）

- `Dockerfile`：固定 `python:3.10.19-slim-bookworm`，安装 core/LangChain/OpenAI runtime，不安装 dev 或 HF embedding 依赖；
- 使用 uid/gid 10001 的非 root `app` 用户，镜像内预建并授权运行目录；
- `scripts/docker-entrypoint.sh`：校验 data/runs/KB 可写，执行 `python -m src.app.db` 后用 `exec` 启动 Uvicorn；
- Uvicorn 显式单 worker、无 reload、无 access log，与当前 SQLite 能力边界一致；
- Dockerfile `HEALTHCHECK` 调用 `/ready`，同时验证 HTTP 与数据库连接；
- `docker-compose.yml` 使用 `chat_api_data`、`chat_api_runs`、`chat_api_kb` 三个命名卷；
- Compose 用容器绝对路径固定 SQLite、run log、Chroma、文档 index、prompt 和 pricing catalog；
- `host.docker.internal:host-gateway` + `OLLAMA_DOCKER_BASE_URL` 解决容器访问 WSL/Linux/Windows 宿主机 Ollama；
- `scripts/docker_start.sh` 一次完成 build、start、等待就绪和 smoke；
- `scripts/docker_smoke_test.py` 使用 Python 标准库且禁用代理，验证 readiness、liveness、native sync/SSE、OpenAI-compatible sync/SSE；
- 开启 API 鉴权时，smoke 仅从当前 shell 的 `CHAT_API_KEY` 读取明文 key，不落盘也不打印；
- 新增 Docker artifact/smoke 单元测试；辅助开发环境全量结果为 `322 passed`；
- CI 新增独立 `docker-smoke` job：真实 build、等待 healthy、执行六链路 smoke、检查 Docker health、最终清理临时卷；
- 目标 WSL 已完成 Docker build、health、三卷持久化、重建后 smoke 和宿主 Ollama 真实连接；实现提交 `5c75a35` 与 GitHub Actions run `32107582238` 的远端双 job 均已通过。

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

### Docker release

- 容器入口的 schema bootstrap 是开发/单机发布边界，不等同于 Alembic 生产迁移；
- `/health` 是 liveness，Docker 使用 `/ready` 作为 healthcheck；
- `docker compose down` 保留命名卷，`docker compose down --volumes` 会删除 SQLite、runs 和 KB；
- 容器内 `127.0.0.1` 不是宿主机，Ollama 默认走 `http://host.docker.internal:11434`；
- Ollama 不进入同一 Compose，避免把 API 生命周期与 GPU、模型权重和推理服务耦合；
- 镜像不包含 `sentence-transformers` 或模型权重，真实 HF embedding 使用自定义镜像扩展；
- 当前 SQLite 只发布单 worker；PostgreSQL、Alembic、Redis 和多实例是扩展路径，不在简历项目收口范围内。

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

以 `.env.example` 为完整模板。宿主机应用读取进程环境变量，不会自动加载 `.env`；Compose 会依次加载模板和可选本地 `.env`：

```bash
cp .env.example .env
set -a && source .env && set +a
```

关键默认值：

```dotenv
APP_LOG_LEVEL=INFO
CHAT_API_PORT=8000
OLLAMA_DOCKER_BASE_URL=http://host.docker.internal:11434
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

Day12 本地与远端结果：

```text
Python 3.10.19
compileall src/scripts/tests warnings-as-errors -> passed
pytest -> 303 passed in 18.38s
skipped -> 0
warnings -> 0
git diff --check -> passed
implementation commit -> a23c92e
GitHub Actions run 32032592555 -> passed
```

Day12 三次 mock baseline 均记录 `git_dirty=false`、commit `a23c92e`、Python 3.10.19、单 worker、隔离 SQLite、MockProvider 和关闭 limiter/quota。每次 1,320 个测量请求，合计 3,960 个；三次结果均保留，未挑选最好的一次。

| Scenario | C | 三次请求数 | RPS 均值 `[范围]` | P50/P95 ms（三次中位数） | TTFT P50/P95 ms | 合并错误率 |
|---|---:|---:|---:|---:|---:|---:|
| `native-sync-c1` | 1 | 300 | 179.527 `[164.901–187.788]` | 4.991 / 6.689 | — | 0% |
| `native-sync-c10` | 10 | 900 | 221.261 `[218.388–226.150]` | 8.691 / 149.267 | — | 0% |
| `native-sync-c50` | 50 | 1,500 | 201.467 `[193.566–207.942]` | 169.073 / 563.727 | — | 49/1,500（3.267%） |
| `native-stream-c1` | 1 | 60 | 2.507 `[2.474–2.524]` | 399.897 / 413.824 | 6.252 / 8.222 | 0% |
| `native-stream-c10` | 10 | 150 | 25.249 `[25.043–25.538]` | 369.962 / 433.856 | 2.261 / 15.402 | 0% |
| `native-stream-c25` | 25 | 300 | 57.855 `[57.441–58.371]` | 382.950 / 517.925 | 2.367 / 45.854 | 0% |
| `openai-sync-c10` | 10 | 600 | 189.509 `[147.730–232.280]` | 9.271 / 138.119 | — | 0% |
| `openai-stream-c10` | 10 | 150 | 23.945 `[23.705–24.260]` | 413.931 / 432.492 | 13.803 / 22.360 | 0% |

关键解释：native sync 的吞吐量在 C10 达到本矩阵高点，C50 时吞吐回落且 tail latency/错误率显著恶化，因此过载拐点只能定位在 C10–C50，不能声称精确最大并发。C50 三次错误率分别为 0%、5.0%、4.8%；失败均为 `QueuePool limit of size 5 overflow 10 reached`，说明当前瓶颈是数据库连接池/持久化路径。流式 mock 的总延迟包含确定性的逐 token sleep，不代表真实模型推理速度。

Day13 目标 WSL 本地发布验收：

```text
Python 3.10.19
pip check -> No broken requirements found
python -W error -m compileall -q src scripts tests -> passed
pytest -q -> 322 passed in 18.24s
shell syntax -> docker-entrypoint.sh / docker_start.sh passed
git diff --check -> passed
Docker Desktop 4.81.0 / Engine 29.6.1 / Compose v5.2.0
Docker image build -> passed
container runtime -> Python 3.10.19, uid/gid 10001(app)
container pip check -> No broken requirements found
Docker health -> healthy, failing streak 0
named-volume mounts -> /app/data, /app/runs, /app/kb
named-volume persistence across down/up -> 3/3 passed
native/OpenAI sync/stream smoke before and after recreate -> 6/6 passed
host.docker.internal -> 192.168.65.254
container -> Windows Ollama /api/tags -> HTTP 200, qwen2.5:7b
```

发布提交前检查：

```bash
git diff --check
git add -A
git diff --cached --check
git status --short
```

本地结果已完整返回并记录。实现提交 `5c75a35` 已通过 GitHub Actions run `32107582238`：Python job `95620047535` 为 `322 passed in 17.65s`，Docker job `95620047554` 为容器 `healthy` 且六链路 smoke 6/6 passed。

## 8. Git 提交边界

应该提交：

- `src/**`、`tests/**`、`scripts/**`；
- `Dockerfile`、`.dockerignore`、`docker-compose.yml`；
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

Provider resilience、Day12 压测和 Day13 Docker 发布收口均已完成。当前简历项目范围内没有必须继续实现的遗留项。

Alembic/PostgreSQL、多实例分布式 limiter/quota 和完整 metrics/tracing backend 属于未来演进边界，不作为本轮 chat-api 简历项目收口的必做项。大路由拆分也不是 Day11 遗留缺陷；只有后续改动确实受阻时，才允许做保持行为不变的独立重构。

## 10. 发布封板状态

Chat-Day12 并发压测、Chat-Day13 Docker 发布单元以及最终状态文档均已完成。

- Day12 实现提交 `a23c92e feat(day12): add reproducible load testing`，GitHub Actions run `32032592555` passed；
- 三次 clean-commit mock baseline 共 3,960 个测量请求，性能数字与 SQLite/QueuePool 高并发边界已记录；
- Day13 实现提交 `5c75a35 chore(day13): add docker release packaging`，GitHub Actions run `32107582238` 的 Python / Docker 两个 job 均 passed；
- 最终状态文档提交 `5d69b98 docs(day13): record final release acceptance` 对应 GitHub Actions run `32108537996`，两个 job 再次 passed；
- `chat-api` 的功能开发、性能基线和 Docker 发布验收已经结束，不再安排新的 Chat-Day 功能开发。

当前只剩仓库级发布动作：

1. 将 README 整理为最终项目首页，并完成最后一次文档 CI；
2. 创建 `v2-langchain-rag-plus -> master` PR；
3. 合并后验证 `master`；
4. 创建最终 release tag。

上述动作不重新打开 Alembic/PostgreSQL、路由大拆分、Multi-Agent、GraphRAG、MCP、分布式 limiter/quota 等范围。

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
39ad9d4 feat(day11): add provider resilience and observability
a23c92e feat(day12): add reproducible load testing
ff47733 docs(day12): record mock load-test baseline
5c75a35 chore(day13): add docker release packaging
```

Day9B cleanup implementation commit：`09a2222 chore(day9b): close repository and CI hygiene`。

Day13 最终实现提交为 `5c75a35 chore(day13): add docker release packaging`，远端验收为 GitHub Actions run `32107582238`，两个 job 均 passed。最终状态文档提交 `5d69b98 docs(day13): record final release acceptance` 对应 GitHub Actions run `32108537996`，两个 job 再次 passed。`chat-api` v2-plus 功能与发布实现保持 closed；后续只进行 README 封板、合并 `master` 和 release tag。
