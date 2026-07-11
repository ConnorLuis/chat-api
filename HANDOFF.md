开始新对话前：**“chat-api 当前位于 `v2-langchain-rag-plus` 分支，定位为 Production-ready LLM Chat Gateway。Chat-Day2–Day6 已完成统一 Provider、OpenAI-compatible 同步/流式、SQLAlchemy 持久化、多会话历史和上下文窗口；Chat-Day7 已完成 UsageRecord 与统一 token accounting；Chat-Day8 已完成 pricing、UsageCost 与 reporting API；Chat-Day9 已完成 API Key 一次性明文创建、HMAC hash 存储、active/revoked、Bearer/X-API-Key、CallerIdentity、公开/受保护路由和真实安全验收。当前 `pytest -q` 为 204 passed，`pytest tests/auth -q` 为 20 passed，GitHub Actions CI 为 success。下一步开始 Chat-Day10：Rate limit / token quota；继续保持 OpenAI-compatible、旧 SSE、RAG、PromptHub、Replay 契约，不要重复 agent-api 的 Agentic RAG / GraphRAG / Multi-Agent / MCP。”**

# HANDOFF（chat-api v2-plus，Chat-Day8 completed）

## 0. 环境与项目

- 环境：WSL2 Ubuntu + conda env=`chatapi`（Python 3.10）
- 项目：`~/projects/chat-api`（GitHub: ConnorLuis/chat-api）
- 已完成 v2 分支：`v2-langchain-rag`
- 当前开发分支：`v2-langchain-rag-plus`
- v1 稳定分支：`master`
- 当前测试：`pytest -q` → `204 passed`
- 当前 CI：GitHub Actions success（Chat-Day9）
- Day7 commit：`bab036c feat(day7): add token usage accounting`
- Day8 test fix：`973b5a6 fix(day8): initialize isolated default test database`
- Day8 feature commit：`22bd6c9 feat(day8): add cost estimation and usage reporting`
- 下一里程碑：Chat-Day10 Rate limit / token quota
- Ollama：安装在 Windows；模型 `qwen2.5:7b` 已 pull
- WSL 访问 Windows Ollama：

```bash
WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"
```

如果做 Error Demo 时临时改成 `http://127.0.0.1:1`，演示结束后要恢复上面的 Windows 网关地址并重启 uvicorn。

---

---

## v2-plus Upgrade Direction（Production-ready LLM Chat Gateway）

当前 `chat-api v2-langchain-rag` 已完成并作为历史基线保留，当前开发已经进入：

```text
v2-langchain-rag-plus
```

该分支的目标不是继续做 Agent，而是升级为：

```text
Production-ready LLM Chat Gateway / 多模型统一接入与流式对话后端系统
```

### 与 agent-api 的边界

`agent-api` 已经覆盖：

```text
Agentic RAG
GraphRAG
Multi-Agent
MCP Integration Layer
```

所以 `chat-api` 后续不要重复：

```text
复杂 Agent Graph
GraphRAG
Multi-Agent Supervisor
MCP 平台化
agent-api 风格的 Agent 编排系统
```

两个项目的定位应保持互补：

```text
agent-api:
  复杂 Agent / RAG / GraphRAG / Multi-Agent / MCP 平台型项目。

chat-api:
  生产级 LLM Chat Gateway / Chat Backend 工程项目。
```

### v2-plus 核心能力目标

```text
多 Provider 接入
OpenAI-compatible /v1/chat/completions
SSE 流式输出
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

### Chat-Day 路线

```text
Chat-Day1:
  新建 v2-langchain-rag-plus 分支，更新 README / HANDOFF，生成本地 LLM_GATEWAY_ROADMAP.md，锁定项目定位。

Chat-Day2:
  Provider 抽象升级，统一 OpenAI / Ollama / Mock。

Chat-Day3:
  OpenAI-compatible /v1/chat/completions API。

Chat-Day4:
  标准 SSE streaming，支持 metadata / delta / usage / final / done / error。

Chat-Day5:
  Conversation / Message 数据库表。

Chat-Day6:
  多会话历史管理与上下文窗口截断。

Chat-Day7:
  Token usage 统计。

Chat-Day8:
  Cost estimation 与 usage summary API。

Chat-Day9:
  API Key 鉴权。

Chat-Day10:
  Rate limit / token quota。

Chat-Day11:
  Prompt cache。

Chat-Day12:
  Provider fallback / retry / timeout。

Chat-Day13:
  Dockerfile + docker-compose。

Chat-Day14:
  health / readiness / metrics。

Chat-Day15:
  pytest + CI 全量补齐。

Chat-Day16:
  压测与性能记录。

Chat-Day17:
  README / HANDOFF / 面试材料整理。

Optional Chat-Day18-Day20:
  简单 Web UI、云部署、项目总结和简历 bullet 打磨。
```

### Chat-Day1 状态

```text
Branch created: v2-langchain-rag-plus
README / HANDOFF positioning: completed
LLM_GATEWAY_ROADMAP.md: local-only, do not commit
Runtime code changed: no
pytest / CI: green
```

### Chat-Day2 状态（completed）

```text
Provider contract: completed
MockProvider: completed
OllamaProvider: completed
OpenAIProvider boundary: completed
ProviderFactory: completed
request-level provider/model override: completed
/chat migration: completed
/chat/stream migration: completed
/prompt/compare migration: completed
pytest -q: 80 passed
GitHub Actions CI: green
```

### Chat-Day3 状态（completed）

```text
POST /v1/chat/completions: completed
OpenAI-compatible request/response/error schemas: completed
OpenAICompatRoute validation adapter: completed
ChatProvider / ProviderFactory reuse: completed
provider gateway extension: completed
OPENAI_COMPAT_DEFAULT_PROVIDER: completed
non-stream chat.completion response: completed
optional usage mapping: completed
stream=true Day4 boundary: completed
n=1 boundary: completed
official Python OpenAI SDK compatibility: completed
pytest tests/openai_compat -q: 7 passed
pytest -q: 87 passed
GitHub Actions CI: green
working tree: clean
```

### Chat-Day4 状态（completed）

```text
stream=true StreamingResponse: completed
Content-Type text/event-stream: completed
chat.completion.chunk schema: completed
assistant role chunk: completed
content delta chunks: completed
finish_reason mapping: completed
stream_options.include_usage: completed
choices=[] usage chunk: completed
data: [DONE]: completed
stream error event: completed
failure stream without [DONE]: completed
official Python OpenAI SDK stream=True: completed
legacy /chat/stream compatibility: completed
pytest tests/openai_compat -q: 12 passed
pytest tests/stream -q: 9 passed
pytest -q: 92 passed
GitHub Actions CI: green
```

### Chat-Day5 状态（completed）

```text
SQLAlchemy 2.0.51: completed
SQLAlchemy>=2.0,<2.1 main dependency: completed
DATABASE_URL: completed
SQLite default database: completed
PostgreSQL migration boundary: completed
Conversation model: completed
Message model: completed
Conversation → Message foreign key: completed
ON DELETE CASCADE: completed
UTCDateTime: completed
lazy Engine / Session factory: completed
init_db / python -m src.app.db: completed
ConversationRepository: completed
MessageRepository: completed
ConversationService: completed
commit / rollback boundary: completed
isolated tmp_path SQLite tests: completed
pytest tests/db -q: 13 passed
pytest tests/openai_compat -q: 12 passed
pytest tests/stream -q: 9 passed
pytest -q: 105 passed
GitHub Actions CI: green
```

### Chat-Day6 状态（completed）

```text
Conversation HTTP API: completed
conversation_id optional request/response boundary: completed
stateless compatibility when conversation_id omitted: completed
Message.sequence_no: completed
UNIQUE(conversation_id, sequence_no): completed
stable history ordering: completed
history + current request merge: completed
recent N user-led turns truncation: completed
token budget truncation: completed
short read session before Provider call: completed
sync success atomic persistence: completed
stream success persistence before usage/done: completed
Provider failure no-write semantics: completed
client disconnect no-partial-assistant semantics: completed
PromptHub / RAG server system prompt not persisted: completed
Conversation missing -> pre-provider HTTP 404: completed
OpenAI-compatible remains stateless: completed
pytest -q: 126 passed
commit: d60c5e3
GitHub Actions: success
```

### Chat-Day7 状态（completed）

```text
UsageRecord ORM and usage_records table: completed
request-level accounting boundary: completed
provider_native/local_estimate/unavailable: completed
chat_sync/chat_stream request kind: completed
succeeded/provider_failed/client_disconnected/persistence_failed: completed
trace/conversation/provider/model/latency association: completed
sync and stream accounting integration: completed
partial stream failure accounting: completed
client disconnect accounting: completed
persistence failure compensation accounting: completed
request-level usage not stored in Message: completed
pytest -q: 147 passed
commit: bab036c
GitHub Actions: success
```

### Chat-Day8 状态（completed）

```text
versioned pricing catalog: completed
provider:model exact and provider:* wildcard matching: completed
separate prompt/completion prices: completed
Decimal fixed precision: completed
UsageCost ORM and usage_costs table: completed
estimated/unknown_price/usage_unavailable: completed
immutable pricing snapshot: completed
UsageRecord + UsageCost one-to-one boundary: completed
Message + UsageRecord + UsageCost atomic success transaction: completed
failure/disconnect/persistence-failure cost accounting: completed
GET /usage/pricing: completed
GET /usage/records: completed
GET /usage/summary: completed
GET /usage/daily: completed
GET /usage/providers: completed
GET /usage/models: completed
time/status/source/cost/provider/model/conversation/request-kind filters: completed
records/group pagination: completed
missing_snapshot historical boundary: completed
currency-separated aggregation: completed
manual API / DB acceptance: passed
pytest tests/chat -q: 20 passed
pytest tests/conversations -q: 7 passed
pytest tests/db -q: 26 passed
pytest tests/stream -q: 24 passed
pytest tests/usage -q: 6 passed
pytest tests/cost -q: 9 passed
pytest tests/usage_api -q: 7 passed
pytest tests/openai_compat -q: 12 passed
pytest -q: 174 passed
test isolation fix commit: 973b5a6
feature commit: 22bd6c9
GitHub Actions: success
```

### Chat-Day9 状态（completed）

```text
one-time plaintext key creation: completed
HMAC-SHA256 + server-side pepper: completed
APIKey ORM/repository/service/CLI: completed
active/revoked/revoked_at: completed
Authorization: Bearer: completed
X-API-Key: completed
CallerIdentity + request.state.caller: completed
GET /auth/whoami: completed
native/OpenAI-compatible auth errors: completed
public/protected route boundary: completed
GET /ready: completed
real HTTP acceptance: passed
real revocation acceptance: passed
database plaintext scan: passed
repository secret scan: passed
Day8 -> Day9 additive schema: passed
pytest tests/auth -q: 20 passed
pytest tests/db -q: 36 passed
pytest -q: 204 passed
GitHub Actions: success
commit message: feat(day9): add API key authentication
```

### 本地路线图文件策略

详细路线图文件：

```text
LLM_GATEWAY_ROADMAP.md
```

该文件只用于本地规划和学习，不进入 git。README、HANDOFF、源码、测试和正式 Day 记录可按阶段提交；不要提交 `LLM_GATEWAY_ROADMAP.md`。

### Chat-Day10 下一步

```text
实现 Rate limit / token quota。

要求：
1. 复用 CallerIdentity.key_id。
2. request rate limit 与 token quota 分离。
3. 明确窗口算法、并发安全和测试时钟。
4. 定义同步、流式、失败、断开时的扣减语义。
5. 原生 429 与 OpenAI-compatible rate_limit_error。
6. 输出 Retry-After、remaining、reset 等信息。
7. 明确单进程 store 与 Redis 分布式边界。
8. pytest 与 GitHub Actions CI 全绿。
```

---

## Chat-Day9：API Key authentication（completed）

### 目标

```text
明文只在创建时返回一次
数据库仅保存 hash/prefix/metadata
active/revoked lifecycle
stable CallerIdentity
public/protected routes
Bearer + X-API-Key
native + OpenAI-compatible errors
real security and migration acceptance
```

### 模块

```text
src/app/auth/{keys,errors,identity,headers,http,dependency,__main__}.py
src/app/api/auth/{routes_auth,schemas}.py
src/app/db/models/api_key.py
src/app/db/repositories/api_keys.py
src/app/services/api_key_service.py
tests/auth/
tests/db/test_api_key_repository.py
tests/db/test_api_key_service.py
```

### 数据模型

```text
APIKey:
  id
  prefix
  key_hash
  name
  status
  created_at
  revoked_at
```

完整 Key：

```text
chat_sk_<public-prefix>_<random-secret>
```

存储：

```text
plaintext returned once
→ HMAC-SHA256 with API_KEY_HASH_PEPPER
→ persist only prefix/hash/metadata
```

### 配置与兼容

```text
API_AUTH_ENABLED=false
API_KEY_HASH_PEPPER=<server-side secret>
```

认证关闭时不访问 api_keys 表，`request.state.caller=None`，保持 Day1-Day8 客户端兼容。认证开启时，受保护 Router 必须提供有效 Key。

### Header 策略

```text
Bearer only -> bearer
X-API-Key only -> x-api-key
both same -> bearer
both different -> api_key_invalid
malformed/empty -> api_key_invalid
missing -> api_key_missing
```

### CallerIdentity

```text
key_id
key_prefix
key_name
authentication_method
authenticated_at
```

不包含 plaintext、hash 或 pepper，为 Day10 rate limit/quota 提供统一 caller 输入。

### 路由边界

公开：

```text
/health
/ready
/docs
/redoc
/openapi.json
/demo
```

受保护：

```text
/chat
/chat/stream
/v1/chat/completions
/conversations/**
/usage/**
/kb/**
/prompts
/prompt/compare
/runs/**
/auth/whoami
```

### 错误契约

原生：

```json
{"detail":{"code":"api_key_missing","message":"API key is required"}}
```

OpenAI-compatible：

```json
{"error":{"message":"API key is required","type":"authentication_error","param":null,"code":"api_key_missing"}}
```

稳定 code：

```text
api_key_missing
api_key_invalid
api_key_revoked
api_key_auth_not_configured
```

### Readiness

`GET /ready` 使用数据库 `SELECT 1`；成功返回 200 ready，失败返回 503 not_ready。`/health` 继续保持纯 liveness。

### 真实验收

```text
public paths without key -> 200
native missing key -> api_key_missing
native X-API-Key -> 200
OpenAI missing key -> authentication_error
OpenAI Bearer -> 200
conflicting headers -> api_key_invalid
revoked key -> api_key_revoked
whoami -> no secret leakage
```

安全验证：

```text
schema has no plaintext/secret/encrypted_key column
stored hash differs from plaintext
HMAC recomputation matches
SQLite DB/WAL/SHM/journal contain no full key
repository contains no real key or pepper
```

迁移验证：

```text
Day8 tables + sentinel row
→ Day9 init_db
→ api_keys added
→ old tables and row preserved
```

### 关键排障

```text
1. shell source day9.env 使历史测试全部 401
   -> root autouse fixture 默认关闭认证，auth fixture 再显式开启。

2. env -u PYTHONPATH 后 src/scripts 无法导入
   -> tests/conftest.py 注入 repo root。

3. auth.__init__ / services 循环导入
   -> auth.__init__ 只导出纯领域对象，具体模块直接导入。

4. 重写 root conftest 丢失 client/isolated_kb_env
   -> 恢复共享 fixture 后再加入 auth isolation。

5. test_api_key_http.py 与 test_chat_mock.py 被重定向清空
   -> 检查 collect 数量和 0-byte test files，最终恢复 204 tests。

6. shell 粘贴误创建 -q、pytest、API_KEY_HASH_PEPPER=... 文件
   -> 删除并采用精确 git add 清单。
```

### 测试与 CI

```text
pytest tests/auth -q -> 20 passed
pytest tests/db -q -> 36 passed
pytest -q -> 204 passed
env -u PYTHONPATH pytest -q -> 204 passed
external API_AUTH_ENABLED isolation -> 16 passed
GitHub Actions -> success
```

### 设计价值

```text
one-time plaintext: DB 泄漏不直接得到可用凭证
HMAC + pepper: 服务端秘密与数据库分离
prefix: 安全识别与运维可观测
CallerIdentity: 认证与 quota/audit 解耦
Router dependency: 不侵入业务 handler
双错误协议: 原生与 OpenAI SDK 都保持稳定契约
feature flag: 支持平滑迁移
真实吊销/明文扫描: 超越单元测试的安全验收
```

### Day9 明确不做

```text
RBAC/scope
rate limit/token quota
key expiration/rotation
Redis auth cache
admin HTTP key management
Alembic production migration
```

---

## Chat-Day8：Cost estimation 与 usage reporting（completed）

### 目标

```text
1. 在 Day7 UsageRecord 上建立版本化价格边界。
2. provider/model 组合分别配置 prompt/completion 单价。
3. 使用 Decimal，避免 float 计费误差。
4. 保存请求发生时的不可变价格与成本快照。
5. 明确 estimated/unknown_price/usage_unavailable。
6. 同步、流式、失败、断开和持久化失败均生成一致 accounting。
7. 提供 records/summary/daily/providers/models 查询与聚合。
8. 不把请求级成本写入 Message。
9. 保持 OpenAI-compatible、旧 SSE、RAG、PromptHub、Replay。
```

### 新增模块

```text
config/pricing_catalog.json

src/app/cost/
├── __init__.py
├── catalog.py
└── estimator.py

src/app/db/models/usage_cost.py
src/app/db/repositories/usage_costs.py
src/app/db/repositories/usage_reports.py

src/app/services/usage_cost_service.py
src/app/services/usage_query_service.py

src/app/api/usage/
├── __init__.py
├── routes_usage.py
└── schemas.py
```

### 价格目录

默认：

```text
version: 2026-07-11-v1
currency: USD
unit_tokens: 1,000,000
mock:*: prompt=0, completion=0
ollama:*: prompt=0, completion=0
```

配置：

```text
PRICING_CATALOG_PATH=config/pricing_catalog.json
```

匹配顺序：

```text
provider:model exact
→ provider:* wildcard
→ no match
```

`pricing_key` 保存实际标准化的 `provider:model`；`matched_pricing_key` 保存目录中命中的 exact/wildcard key。

### Decimal 与成本状态

数据库金额精度：

```text
NUMERIC(24, 12)
COST_QUANTUM = 0.000000000001
```

API 金额使用字符串，不输出 JSON float。

状态：

```text
estimated:
  token 已知且命中价格；
  显式零价格也属于 estimated。

unknown_price:
  token 已知但价格未知；
  金额必须为 NULL，不能伪装成 0。

usage_unavailable:
  token 不可用；
  金额必须为 NULL。
```

### UsageCost 数据模型

```text
request_id PK/FK -> usage_records.request_id
pricing_key
matched_pricing_key
pricing_version
currency
unit_tokens
cost_status
prompt_price_per_unit
completion_price_per_unit
prompt_cost
completion_cost
estimated_cost
created_at
```

价格快照写入后不受未来目录修改影响。

历史 Day7 记录没有 `UsageCost` 时：

```text
cost = null
cost_status filter = missing_snapshot
```

查询层不会按当前价格回填历史。

### 事务边界

```text
stateful success:
  Message + UsageRecord + UsageCost one transaction。

stateless success:
  UsageRecord + UsageCost one transaction。

provider_failed:
  已知 partial usage -> estimated/unknown_price；
  usage unavailable -> usage_unavailable。

client_disconnected:
  不保存 partial Message；
  保存 partial usage 与成本快照。

persistence_failed:
  主事务回滚；
  补偿写入 consumed UsageRecord + UsageCost。
```

`Message` 仍只保存消息级 `token_count`，没有 `estimated_cost/pricing_version/currency`。

### Usage API

```text
GET /usage/pricing
GET /usage/records
GET /usage/summary
GET /usage/daily
GET /usage/providers
GET /usage/models
```

通用过滤：

```text
start_time inclusive
end_time exclusive
status
usage_source
cost_status
provider
model
conversation_id
request_kind
limit
offset
```

时间必须带 timezone；naive datetime 返回 HTTP 422。

聚合：

```text
request_count
statuses
usage_sources
prompt_tokens
completion_tokens
total_tokens
total_latency_ms
average_latency_ms
cost_statuses
costs_by_currency
```

不同 currency 不直接相加。

### 分阶段完成

```text
Day8-A:
  pricing catalog + estimator + UsageCost model/repository/service
  pytest -q -> 162 passed

Day8-B:
  sync/stream/failure/disconnect atomic integration
  response/SSE cost metadata
  pytest -q -> 167 passed

Day8-C:
  pricing/records/summary/daily/providers/models APIs
  filters/pagination/aggregation
  pytest -q -> 174 passed

Day8-D:
  manual API/DB acceptance
  CI isolation and complete commit verification
  GitHub Actions -> success
```

### 手动验收结果

```text
usage_records = 6
usage_costs snapshots = 6
stateful messages = 6
sequence_no = [1,2,3,4,5,6]

mock sync/stream/stateless:
  local_estimate
  estimated
  matched mock:*
  zero USD API billing snapshot

ollama success:
  provider_native
  estimated
  matched ollama:*

sync/stream connection failure:
  provider_failed
  usage_source unavailable
  cost_status usage_unavailable
  amount NULL
  no Message write

client disconnect:
  deterministic test passed
  partial accounting persisted
```

Summary arithmetic:

```text
request_count = 6
succeeded = 4
provider_failed = 2
prompt_tokens = 178
completion_tokens = 73
total_tokens = 251
total_latency_ms = 3632
average_latency_ms = 605.333
estimated = 4
usage_unavailable = 2
missing_snapshot = 0
```

### CI 排障

#### 1. 默认 SQLite schema 依赖

第一次 Day8 CI 失败：

```text
local database had usage_costs
fresh CI database did not
legacy tests used module-level TestClient(app)
```

结果：

```text
/chat -> 500
/chat/stream -> error event
run log tests did not reach append_jsonl
```

修复：

```text
tests/conftest.py session-scoped autouse fixture
→ isolated temp SQLite
→ init_db(engine)
→ complete current Base.metadata
```

#### 2. 测试先推送、实现未推送

第二次 CI 在 collection 阶段失败：

```text
No module named src.app.cost
No module named src.app.api.usage
cannot import UsageCost
```

原因是测试文件已提交，而 Day8 实现仍是 untracked/staged local files。

修复：

```text
逐项检查 required files
git diff --cached --name-status
git ls-files
完整暂存 config/src/tests
```

#### 3. CRLF 与误创建文件

多行 shell 粘贴过程中出现：

```text
=
ses import dataclass
tatus --short
ts
```

并有 Markdown/Python CRLF 导致 `git diff --check` 噪声。

修复：

```text
删除误文件
统一 LF
同时执行：
git diff --check
git diff --cached --check
```

### 测试与提交

```text
pytest tests/chat -q -> 20 passed
pytest tests/conversations -q -> 7 passed
pytest tests/db -q -> 26 passed
pytest tests/stream -q -> 24 passed
pytest tests/usage -q -> 6 passed
pytest tests/cost -q -> 9 passed
pytest tests/usage_api -q -> 7 passed
pytest tests/openai_compat -q -> 12 passed
pytest -q -> 174 passed
```

Git：

```text
973b5a6 fix(day8): initialize isolated default test database
22bd6c9 feat(day8): add cost estimation and usage reporting
GitHub Actions CI: success
```

### 设计价值（面试可讲）

```text
1. Usage 和 Cost 分表：
   token 事实与价格快照职责分离。

2. 不可变价格快照：
   价格目录变化不会篡改历史账单。

3. unknown_price 不等于 0：
   避免把“无法计价”误报成“免费”。

4. 使用 Decimal：
   避免浮点累计误差和 JSON float 精度丢失。

5. 终态和计费解耦：
   provider_failed/disconnected 也可能已经消费 token。

6. 多币种分组：
   不产生无意义的跨币种总和。

7. historical missing_snapshot：
   明确兼容 Day7 历史，而不是查询时静默重算。
```

---

## Chat-Day7：Token usage accounting（completed）

### 目标

```text
1. 建立独立请求级 UsageRecord。
2. 明确 Provider 原生 usage 与本地估算 usage。
3. 统一同步与流式 accounting。
4. 保存 prompt/completion/total token。
5. 关联 trace/conversation/provider/model/latency。
6. 明确成功、Provider 失败、客户端断开、持久化失败。
7. 不把请求级 usage 写入 Message。
8. 为 Day8 cost estimation 提供事实边界。
```

### UsageRecord

```text
request_id
trace_id
conversation_id
request_kind
provider
model
status
usage_source
prompt_tokens
completion_tokens
total_tokens
latency_ms
error_type
created_at
```

Usage source：

```text
provider_native
local_estimate
unavailable
```

Status：

```text
succeeded
provider_failed
client_disconnected
persistence_failed
```

### 关键语义

```text
Provider 原生 usage 完整:
  使用 provider_native。

Provider 未提供完整 usage:
  对最终 request messages 和 completion text 做 local_estimate。

无法获得可靠 token:
  unavailable + NULL，不写 0。

stateful success:
  Message + UsageRecord atomic commit。

stateless:
  不写 Message，但仍写 UsageRecord。

failure/disconnect:
  不写 incomplete Message；
  仍保存请求级 accounting。

persistence failure:
  主事务回滚后保留 consumed usage。
```

### 测试与提交

```text
pytest -q -> 147 passed
commit -> bab036c feat(day7): add token usage accounting
GitHub Actions CI -> success
```
## Chat-Day6：多会话历史与上下文窗口（completed）

### 目标

```text
1. 将 Chat-Day5 Conversation / Message 持久化基础接入聊天主链路。
2. 明确 conversation_id 的可选请求/响应边界。
3. 保存 user / assistant 消息。
4. 使用稳定的 sequence_no 加载历史。
5. 将历史与当前请求合并后发送给 Provider。
6. 支持最近 N 轮与 token budget 截断。
7. 明确同步、流式、Provider 失败和客户端断开的事务语义。
8. 提供 Conversation / Message 最小 HTTP 查询能力。
9. 保持 RAG、PromptHub、Replay、OpenAI-compatible 与旧 SSE 兼容。
```

### 核心边界

```text
conversation_id omitted:
  保持原有无状态请求；
  不读取数据库；
  不写入 Conversation / Message。

conversation_id provided:
  Conversation 必须预先存在；
  服务端读取持久化历史；
  body.messages 只代表本次新增消息；
  Provider 完整成功后保存本轮消息。
```

聊天路由不会隐式创建 Conversation；新会话通过：

```text
POST /conversations
```

创建。

OpenAI-compatible：

```text
POST /v1/chat/completions
```

继续保持独立无状态，不读取或写入 Conversation 历史。

### 新增模块

```text
src/app/api/conversations/
├── __init__.py
├── routes_conversations.py
└── schemas.py

src/app/conversations/
├── __init__.py
├── context_window.py
└── history.py
```

新增测试：

```text
tests/conversations/
├── conftest.py
├── test_context_window.py
└── test_conversation_api.py

tests/chat/test_chat_conversation_history.py
tests/stream/test_stream_conversation_history.py
```

### Message ordering

Message 模型新增：

```text
sequence_no INTEGER NOT NULL
CHECK(sequence_no >= 1)
UNIQUE(conversation_id, sequence_no)
```

Repository 使用：

```text
MAX(sequence_no) + 1
```

分配下一序号，并固定按：

```text
sequence_no ASC
```

查询历史。

设计原因：

```text
created_at 可能出现相同时间戳；
UUID 不能表达业务顺序；
sequence_no 是 Conversation 内显式、稳定、可测试的消息顺序。
```

### ConversationService

新增：

```text
NewMessage
append_messages()
list_recent_messages()
```

`append_messages()` 在同一事务中追加多条消息，用于原子保存：

```text
当前 request messages
+
最终 assistant message
```

Repository 只负责 `add / flush / query`，Service 继续负责 `commit / rollback`。

### Context window

配置：

```text
CONVERSATION_HISTORY_MAX_TURNS=10
CONVERSATION_CONTEXT_TOKEN_BUDGET=4096
CONVERSATION_HISTORY_FETCH_LIMIT=500
```

估算规则：

```text
estimate_text_tokens(content)
  = max(1, ceil(len(content) / 2))

estimate_message_tokens(message)
  = estimate_text_tokens(content) + 4
```

合并顺序：

```text
PromptHub / RAG server system prompt
→ 截断后的持久化历史
→ 当前 body.messages
```

截断原则：

```text
当前消息永不删除；
system prompt 计入预算；
从最旧历史开始淘汰；
优先保留最近完整 user-led turns；
不保留不完整历史轮次。
```

修复过一个测试边界：

```text
current 消息估算 8 tokens
最新完整 turn 估算 28 tokens
总计 36 tokens

测试原预算 35 时只能保留 current；
将预算修正为 36，并断言 estimated_tokens == 36。
```

实现逻辑无需修改。

### Conversation HTTP API

```text
POST   /conversations
GET    /conversations
GET    /conversations/{conversation_id}
PATCH  /conversations/{conversation_id}
DELETE /conversations/{conversation_id}
GET    /conversations/{conversation_id}/messages
```

支持：

```text
创建
分页列表
单条查询
重命名
删除
消息分页查询
```

不存在的 Conversation 返回 HTTP 404。

### 同步 /chat 调用链

```text
读取 conversation_id
→ 使用短 Session 验证 Conversation 并加载历史
→ 释放 DB Session
→ PromptHub / RAG
→ build_context_window()
→ Provider.chat()
→ Provider 完整成功
→ 当前 request messages + assistant 原子落库
→ 返回 ChatResponse
```

响应新增可选字段：

```text
conversation_id
```

并保留原有：

```text
session_id
```

同步 Provider 失败：

```text
HTTP 502
不保存当前 user
不保存 assistant
```

Conversation 在 Provider 调用期间被删除或持久化失败时，不返回一个看似成功但未落库的 stateful response。

### 流式 /chat/stream 调用链

```text
在 StreamingResponse 建立前验证 Conversation
→ meta
→ token*
→ 内存累积完整 assistant
→ Provider 正常结束
→ 原子保存当前 request messages + assistant
→ usage
→ done
```

关键不变量：

```text
persist < usage < done
```

Provider 失败：

```text
meta → token*（可能为 0）→ error
无 usage
无 done
不落库
```

客户端断开：

```text
传播 asyncio.CancelledError
关闭 Provider async iterator
不保存部分 assistant
```

数据库操作通过：

```text
run_in_threadpool()
```

执行，避免同步 SQLAlchemy 操作阻塞 async event loop。

### PromptHub / RAG 边界

PromptHub / RAG 生成的 server system prompt：

```text
参与 token budget
参与当前 Provider 请求
不写入 Message 表
```

RAG query 仍从当前 `body.messages` 中提取，不会误用旧历史中的最后一个 user 问题。

### 手动验收

通过的成功路径：

```text
Conversation create/get/list/rename
无状态 /chat 不落库
两轮同步会话落库
流式会话加载 4 条历史
流式成功事件 meta → token* → usage → done
同步 + 流式后 sequence_no 1..6 连续
不存在 Conversation 的 sync/stream 均在 Provider 前 HTTP 404
```

数据库实查最终确认：

```text
sequence_no unique: True
sequence_no continuous: True
```

失败路径使用独立服务：

```text
port: 8001
OLLAMA_BASE_URL=http://127.0.0.1:1
```

同步失败：

```text
HTTP 502
before message count == after message count
```

流式失败：

```text
event: meta
event: error
无 event: usage
无 event: done
before message count == after message count
```

手动验收中曾出现两个操作问题：

```text
1. get_session_factory() 返回 sessionmaker，
   正确用法是 session_factory = get_session_factory();
   with session_factory() as session。

2. 新失败服务最初因 8000 端口占用未启动，
   请求实际打到旧的正常 Ollama 服务；
   后改用 8001 独立失败服务完成验收。
```

这些是验收脚本/进程管理问题，不是业务代码缺陷。

### 测试与 CI

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
```

Git：

```text
d60c5e3 feat(day6): add conversation history and context window
```

GitHub Actions：

```text
workflow: CI
run id: 29145652536
branch: v2-langchain-rag-plus
sha: d60c5e3
event: push
status: completed
result: success
created: 2026-07-11T08:08:57Z
```

### 兼容性结论

```text
无 conversation_id 的 /chat 保持无状态
无 conversation_id 的 /chat/stream 保持原事件契约
/v1/chat/completions 保持独立无状态
/prompt/compare 未接入 Conversation
RAG contract 保持
PromptHub contract 保持
Replay contract 保持
OpenAI SDK 非流式 / stream=True 保持通过
```

### 设计价值（面试可讲）

```text
1. 显式 stateful/stateless boundary：
   不强迫所有调用方使用数据库历史。

2. DB Session 与模型调用解耦：
   慢 Provider 请求期间不占用数据库连接。

3. 完整成功后写入：
   避免 user-only 或 partial assistant 污染会话。

4. 稳定 sequence_no：
   明确解决时间戳/UUID 不能表达严格业务顺序的问题。

5. 完整 turn 截断：
   比简单截断最近 N 条 message 更符合对话语义。

6. streaming commit barrier：
   只有数据库提交成功后才发送 usage/done，
   保证客户端看到 done 时会话状态已经持久化。
```

### 下一里程碑

```text
Chat-Day7: Token usage accounting
```

---

## Chat-Day2：Provider 抽象升级（completed）

### 目标

```text
1. 梳理现有 LLMEngine / Mock / Ollama 调用链。
2. 设计 ChatProvider 协议。
3. 统一 Provider 请求、响应、流式 Chunk 和 Usage 边界。
4. 保留 MockProvider 用于 deterministic tests / CI。
5. 保留 OllamaProvider 用于本地模型。
6. 新增 OpenAIProvider 边界。
7. 新增 ProviderFactory。
8. 支持请求级 provider/model override。
9. 保持 /chat、/chat/stream、/prompt/compare 及 RAG/SSE/error contract 兼容。
```

### 新增 Provider 层

```text
src/app/llm/providers/
├── __init__.py
├── adapters.py
├── base.py
├── errors.py
├── factory.py
├── mock.py
├── ollama.py
├── openai.py
└── schemas.py
```

统一边界：

```text
ChatProvider
ProviderMessage
ProviderChatRequest
ProviderChatResponse
ProviderChatChunk
ProviderUsage
```

主调用链：

```text
/chat          → get_chat_provider() → provider.chat()
/chat/stream   → get_chat_provider() → provider.stream()
/prompt/compare→ get_chat_provider() → provider.chat()
```

### Provider 实现

- `MockProvider`：无网络、确定性输出，继续作为 CI 和契约测试默认 Provider。
- `OllamaProvider`：保留原 `/api/generate` 协议，支持请求级 `model` 覆盖，并映射统一 response/chunk/usage。
- `OpenAIProvider`：支持 OpenAI / OpenAI-compatible endpoint；SDK 通过 `requirements-openai.txt` 按需安装并懒加载。
- OpenAI 配置边界：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`、`OPENAI_TIMEOUT_S`。
- `ProviderFactory`：标准化 provider 名称，构造 `mock|ollama|openai`，非法名称抛清晰异常。

### Schema 与兼容性

- `ChatRequest.provider` 和 `PromptCompareRequest.provider` 扩展为 `mock|ollama|openai`。
- 两者新增可选 `model` 字段；请求级模型优先于 Provider 默认模型。
- API 层 schema 与 Provider 内部 schema 分离，RAG、PromptHub、session 等字段不会污染模型 Provider。
- `/chat` 同步错误继续返回 HTTP 502 + structured detail。
- `/chat/stream` 继续返回 HTTP 200 SSE，业务错误通过 `event:error` 传递。
- SSE 成功顺序保持 `meta → token* → usage → done`。
- Provider 结束分片中的空 `delta` 不会被暴露为空 token 事件。

### 测试与排障

新增/扩展：

```text
tests/providers/
tests/chat/test_chat_provider_compatibility.py
tests/stream/test_stream_provider_compatibility.py
tests/prompt/test_prompt_compare_provider_compatibility.py
```

一次流式测试失败并非后端丢失空格，而是测试 SSE parser 使用 `strip()` / `lstrip()` 删除了合法空格 token。修复为只移除 SSE 冒号后的一个可选分隔空格，并避免对整个 event block 执行 `strip()`。

最终验收：

```text
Provider tests: 13 passed
Chat tests: 8 passed
Stream tests: 9 passed
Prompt tests: 3 passed
pytest -q: 80 passed
GitHub Actions CI: green
```

### 当前兼容代码

旧 `src/app/llm/engines/` 暂时保留，避免不必要的大范围删除；当前聊天业务入口已经不再直接调用 `get_engine()`、`engine.generate()` 或 `engine.stream()`。后续是否删除或改成 adapter，应在兼容测试覆盖充分后单独处理。

### 下一里程碑

```text
Chat-Day4: OpenAI-compatible SSE streaming
```

---

## Chat-Day3：OpenAI-compatible `/v1/chat/completions`（completed）

### 目标

```text
1. 复用 ChatProvider / ProviderFactory。
2. 新增独立 OpenAI-compatible request / response / error schema。
3. 完成非流式 POST /v1/chat/completions。
4. 为 stream=true 建立明确边界，不提前实现半套 SSE。
5. 保持 /chat、/chat/stream、/prompt/compare、RAG、PromptHub、Replay 兼容。
6. pytest 与 CI 全绿。
```

### 新增模块

```text
src/app/api/openai_compat/
├── __init__.py
├── errors.py
├── route.py
├── routes_chat_completions.py
└── schemas.py
```

测试：

```text
tests/openai_compat/test_chat_completions.py
```

### 调用链

```text
POST /v1/chat/completions
  → OpenAIChatCompletionRequest
  → provider override 或 OPENAI_COMPAT_DEFAULT_PROVIDER
  → get_chat_provider()
  → build_provider_request()
  → provider.chat()
  → ProviderChatResponse
  → OpenAIChatCompletionResponse
```

新路由不调用旧 `/chat` 路由函数，因此不会把 RAG、PromptHub、Replay、session 或旧 metadata 契约耦合进 OpenAI-compatible API。

### 请求子集

当前支持：

```text
model
messages（纯文本）
roles：developer/system/user/assistant
temperature
top_p
max_tokens
max_completion_tokens
n=1
stream=false
user
provider（chat-api 网关扩展字段）
```

当前明确不支持：

```text
stream=true 标准 chunk（Chat-Day4）
n > 1
tools / tool_calls / function
多模态 content parts
logprobs 计算
response_format
```

### 非流式响应

响应结构：

```text
id: chatcmpl-...
object: chat.completion
created: Unix seconds
model
choices[0].index
choices[0].message.role=assistant
choices[0].message.content
choices[0].finish_reason
choices[0].logprobs=null
usage（仅在 Provider 返回完整统计时存在）
```

未知 usage 不伪造为零，而是省略。

### 错误契约

`OpenAICompatRoute` 只转换 `/v1` 兼容路由的 `RequestValidationError`，不会注册全局异常处理器，因此旧接口的 FastAPI/HTTP 错误契约不受影响。

统一错误形状：

```json
{
  "error": {
    "message": "...",
    "type": "invalid_request_error",
    "param": "stream",
    "code": "streaming_not_supported_yet"
  }
}
```

关键边界：

```text
stream=true → HTTP 400 / streaming_not_supported_yet
n > 1 → HTTP 400 / unsupported_value
非法请求 → HTTP 400 / invalid_request
Provider 调用失败 → HTTP 502 / provider_error
非法默认 Provider 配置 → HTTP 500 / invalid_gateway_configuration
```

### Provider 选择

```text
body.provider
  → OPENAI_COMPAT_DEFAULT_PROVIDER
  → 默认 mock
```

标准 OpenAI SDK 可通过：

```python
extra_body={"provider": "mock"}
```

传递网关扩展字段。

### 真实兼容性验证

本地安装并验证：

```text
openai 2.45.0
```

客户端：

```python
client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="local-test-key",
)
```

实测结果：

```text
client.chat.completions.create() 调用成功
completion.object == "chat.completion"
completion.choices[0].message.content 正常
completion.choices[0].finish_reason == "stop"
completion.choices[0].logprobs is None
completion.usage is None（MockProvider 无真实 token 统计）
extra_body provider override 调用成功
```

当前 `local-test-key` 只满足 SDK 客户端初始化；API Key 鉴权安排在 Chat-Day9。

### 实现过程中的问题

#### 1. 新路由最初全部返回 404

原因：

```text
main.py 路由注册补丁依赖文件结尾换行；
include marker 未匹配；
脚本提前退出；
openai_compat_router 未被 include_router()。
```

修复：

```text
使用不依赖尾部换行的精确字符串匹配；
注册 openai_compat_router；
直接枚举 app.routes 确认 /v1/chat/completions 存在。
```

#### 2. `logprobs: null` 被响应过滤掉

原因：

```text
response_model_exclude_none=True
```

同时删除了：

```text
choices[0].logprobs = null
```

但直接关闭该选项又会让未知 usage 变成：

```text
usage: null
```

修复：

```text
成功响应手动 model_dump(exclude_none=True)
→ 省略未知 usage
→ 显式补回 choices[].logprobs = null
→ JSONResponse 返回
```

### 验收

```text
pytest tests/openai_compat -q
7 passed

pytest -q
87 passed in 6.10s / 6.11s

GitHub Actions CI
green

commit
732f084 feat(day3): add OpenAI-compatible chat completions

working tree
clean
```

### 兼容性结论

```text
/chat 未修改
/chat/stream 未修改
/prompt/compare 未修改
RAG 未修改
PromptHub 未修改
Replay 未修改
旧 SSE 成功/失败事件契约未修改
```

### 下一里程碑

```text
Chat-Day4: OpenAI-compatible SSE streaming
```

---

## Chat-Day4：OpenAI-compatible SSE streaming（completed）

### 目标

```text
1. 复用 OpenAIChatCompletionRequest 与 ChatProvider.stream()。
2. stream=true 返回 text/event-stream。
3. 每个数据块使用 data: {JSON}。
4. object 固定为 chat.completion.chunk。
5. 首个 chunk 建立 assistant role。
6. 后续 chunk 输出 content delta。
7. 正确映射 finish_reason。
8. 可选 usage chunk 与 ProviderUsage 对齐。
9. 最终输出 data: [DONE]。
10. Provider 失败时输出流内 OpenAI-compatible error。
11. 保持旧 /chat/stream 契约不变。
```

### 新增与修改

```text
M  src/app/api/openai_compat/routes_chat_completions.py
M  src/app/api/openai_compat/schemas.py
A  src/app/api/openai_compat/streaming.py
M  tests/openai_compat/test_chat_completions.py
A  tests/openai_compat/test_chat_completions_stream.py
```

未修改：

```text
src/app/api/routes_chat.py
src/app/api/prompt/routes_prompt.py
src/app/llm/providers/
src/app/rag/
```

### 流式调用链

```text
POST /v1/chat/completions
  → OpenAIChatCompletionRequest
  → get_chat_provider()
  → build_provider_request()
  → provider.stream()
  → ProviderChatChunk*
  → OpenAI streaming adapter
  → data: {chat.completion.chunk JSON}*
  → optional usage chunk
  → data: [DONE]
```

### 正常顺序

```text
role chunk
→ content delta chunk*
→ finish chunk
→ usage chunk（可选）
→ data: [DONE]
```

### Usage 规则

只有请求 `stream_options.include_usage=true`，且 ProviderUsage 完整时，才输出 `choices=[]` usage chunk。不完整 usage 不伪造为零。

### 错误语义

StreamingResponse 建立后无法切换为 HTTP 502，因此 Provider 失败时输出：

```text
data: {"error":{"message":"...","type":"api_error","param":null,"code":"provider_error"}}

```

失败流不输出 finish chunk、usage chunk 或 `[DONE]`。

### 兼容隔离

```text
/v1/chat/completions:
  data-only SSE
  chat.completion.chunk
  [DONE]

/chat/stream:
  event: meta
  event: token
  event: usage
  event: done
  event: error
```

Day4 通过独立 `streaming.py` adapter 实现，没有修改旧路由。

### 测试与实测

```text
tests/openai_compat/test_chat_completions.py -> 6 passed
tests/openai_compat/test_chat_completions_stream.py -> 6 passed
tests/openai_compat -> 12 passed
tests/stream -> 9 passed
pytest -q -> 92 passed in 6.82s
GitHub Actions CI -> green
```

curl 与官方 Python OpenAI SDK 的 `stream=True` 均已实测通过。

### 下一里程碑

```text
Chat-Day5: Conversation / Message database tables
```

---

## Chat-Day5：Conversation / Message persistence foundation（completed）

### 目标

```text
SQLite 开发存储
PostgreSQL 迁移边界
Conversation / Message ORM
外键关系与级联删除
数据库初始化与 session
repository/service 分层
隔离测试数据库
最小 CRUD 与事务测试
保持现有 API 不变
```

### 技术方案

```text
SQLAlchemy 2.0.51
requirements: SQLAlchemy>=2.0,<2.1
default DATABASE_URL: sqlite:///./data/chat_api.db
future PostgreSQL: postgresql+psycopg://...
```

Day5 不引入：

```text
Alembic
psycopg
asyncpg
aiosqlite
```

当前只建立可迁移 ORM 边界；正式 PostgreSQL 驱动和 migration 在后续部署阶段接入。

### 数据模型

Conversation：

```text
id
title
created_at
updated_at
```

Message：

```text
id
conversation_id
role
content
provider
model
token_count
created_at
```

外键：

```text
messages.conversation_id
  → conversations.id
  → ON DELETE CASCADE
```

### 时间边界

新增 `UTCDateTime`：

```text
SQLite:
  写入 UTC naive；
  读取恢复 UTC-aware。

PostgreSQL:
  timezone-aware DateTime。
```

### 数据库与 session

```text
build_engine()
build_session_factory()
get_engine()
get_session_factory()
init_db()
get_db_session()
```

默认 engine/session factory 懒加载，单纯 import 不会创建本地数据库。

SQLite 连接时：

```text
check_same_thread=False
PRAGMA foreign_keys=ON
```

### Repository / Service

Repository：

```text
ConversationRepository
MessageRepository
```

职责：

```text
add
flush
query
delete
不 commit
```

Service：

```text
ConversationService
```

职责：

```text
输入规范化
Conversation 存在性检查
跨 repository 编排
commit
rollback
```

### 测试隔离

每个测试使用：

```text
tmp_path/chat_api_test.db
```

不会污染：

```text
data/chat_api.db
kb/chroma/chroma.sqlite3
```

### 运行验证

```text
python -m src.app.db
database initialized: sqlite:///./data/chat_api.db

tables:
['conversations', 'messages']
```

`data/` 已加入 `.gitignore`。

### 测试

```text
tests/db/test_session.py
tests/db/test_conversation_repository.py
tests/db/test_message_repository.py
tests/db/test_conversation_service.py
```

覆盖：

```text
schema 初始化
foreign_keys=ON
Conversation CRUD
Message CRUD
外键约束
级联删除
role/content/token_count 校验
service commit / rollback
临时数据库隔离
```

验收：

```text
pytest tests/db -q
13 passed

pytest tests/openai_compat -q
12 passed

pytest tests/stream -q
9 passed

pytest -q
105 passed in 7.25s

GitHub Actions CI
green
```

### 兼容性边界

未修改：

```text
/chat
/chat/stream
/v1/chat/completions
/prompt/compare
Provider
RAG
PromptHub
Replay
```

未提前实现：

```text
自动持久化聊天消息
自动历史加载
上下文窗口截断
Conversation HTTP API
usage/cost 落库
```

### 下一里程碑

```text
Chat-Day6: 多会话历史与上下文窗口截断
```

---

## v2-langchain-rag Archive Below

以下内容保留为 `chat-api v2-langchain-rag` Day1-Day30 归档记录。

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

## 2. 已完成进度概览（Day1–Day30）

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


### Day27：RAG Observability：latency breakdown + trace 增强

- Day27 已闭环，分为三段：
  - Day27-A：`feat(day27): add rag backend observability timing`
  - Day27-B：`feat(day27): expose rag observability in chat responses`
  - Day27-C：`test(day27): assert langchain route rag observability`
- Day27-A：
  - `NativeRAGBackend` 与 `LangChainRAGBackend` 写入统一 timing schema：
    - `embedding_ms`
    - `retrieval_ms`
    - `rerank_ms`
    - `context_build_ms`
    - `total_ms`
  - timing 与 backend marker 写入 `RAGContextResult.extra`。
  - native extra：`backend=native`。
  - langchain extra：`backend=langchain`、`vectorstore=langchain_chroma`。
  - 新增/更新：
    - `tests/rag/test_native_backend_observability.py`
    - `tests/rag/test_langchain_backend_contract.py`
- Day27-B：
  - `RagMetadata` 新增：
    - `backend`
    - `vectorstore`
    - `embedding_ms`
    - `retrieval_ms`
    - `rerank_ms`
    - `context_build_ms`
    - `total_ms`
  - `/chat` 的 `metadata.rag` 透传 backend/timing。
  - `/chat/stream` 的 `meta.rag`、`usage.rag`、`error.rag` 透传 backend/timing。
  - 更新：
    - `tests/chat/test_chat_rag_contract.py`
    - `tests/stream/test_stream_rag_contract.py`
- Day27-C：
  - 新增 `tests/rag/test_langchain_route_observability.py`。
  - 验证 `RAG_BACKEND=langchain` 时：
    - `/chat metadata.rag.backend == "langchain"`
    - `/chat/stream meta.rag.backend == "langchain"`
    - `/chat/stream usage.rag.backend == "langchain"`
    - `vectorstore == "langchain_chroma"`
    - timing 字段存在且为非负整数。
  - 该测试用 `pytest.importorskip` 保护 CI，避免 optional LangChain 依赖污染基础 CI。
- 本地验收：
  - `pytest tests/rag/test_native_backend_observability.py -q` → 1 passed
  - `pytest tests/rag/test_langchain_backend_contract.py -q` → 2 passed
  - `pytest tests/chat/test_chat_rag_contract.py -q` → 2 passed
  - `pytest tests/stream/test_stream_rag_contract.py -q` → 2 passed
  - `pytest tests/rag/test_langchain_route_observability.py -q` → 2 passed
  - `pytest -q` → 52 passed（本地安装 LangChain optional deps 时）
- 远程验收：
  - Day27-A / Day27-B / Day27-C GitHub Actions 均已通过。
- 注意：RAG / Chroma 测试可能修改 `kb/chroma/chroma.sqlite3`，这是运行时产物，不应提交。



### Day28：Hybrid RAG：vector retrieval + lexical retrieval + fusion rerank

- Day28 已完成 Hybrid RAG 路线，目标是在不改变 `/chat` 与 `/chat/stream` request contract 的前提下，把原有向量检索升级为：
  - vector retrieval：保留 Chroma / LangChain Chroma 向量召回；
  - lexical scoring：补充关键词、标题、source、exact phrase 等词面信号；
  - fusion rerank：将 vector score、lexical score 与既有 query-aware rule bonus 融合排序。
- Day28-A：`feat(day28): add hybrid rag fusion rerank`
  - 修改：`src/app/kb/rag_context.py`、`src/app/rag/native_backend.py`、`src/app/rag/langchain_backend.py`、`tests/kb/test_hybrid_rag_rerank.py`、backend observability tests。
  - 新增常量：`HYBRID_RETRIEVAL_MODE="hybrid"`、`FUSION_METHOD="vector_lexical"`、`VECTOR_WEIGHT=0.7`、`LEXICAL_WEIGHT=0.3`。
  - `rerank_hits()` 从“vector score + rule bonus”升级为“vector score + lexical score + query-aware rule bonus”。
  - native/langchain backend 的 `RAGContextResult.extra` 增加 `retrieval_mode/fusion/vector_weight/lexical_weight`。
  - 本地验收：`pytest tests/kb/test_hybrid_rag_rerank.py -q` → 5 passed；`pytest -q` → 57 passed。
- Day28-B：`feat(day28): expose hybrid rag fusion observability`
  - `RagMetadata` 增加 Hybrid observability 字段：`retrieval_mode`、`fusion`、`vector_weight`、`lexical_weight`。
  - `/chat metadata.rag` 与 `/chat/stream meta.rag / usage.rag / error.rag` 均暴露这些字段。
  - 测试锁定 native 与 langchain route 层都能看到 `retrieval_mode == "hybrid"`、`fusion == "vector_lexical"`、`vector_weight == 0.7`、`lexical_weight == 0.3`。
- Day28-C：`fix(day28): make rag eval citation matching robust`
  - 第一次 Day28-C eval 失败：`answer_hit_rate=10%`、`citation_hit_rate=5%`。原因是 live KB 仍是 demo 数据，citations 指向 `source=demo` / `title=RAG Demo Note`，不是 QA20 对应的 `docs/kb_seed/01-11`。
  - 重建 KB 为 `docs/kb_seed/01-11` 后：`answer_hit_rate=95%`，但 `citation_hit_rate=0%`、`title_hit_rate=0%`。原因是 `scripts/eval_qa_rag.py` 使用 exact match，而 QA20 的 `expected_sources=["kb_seed"]` 是来源类别标记，实际 `citation.source` 是 `docs/kb_seed/07_KB Ingest & Search.md` 这类完整路径；旧入库方式还可能把 `title` 写成 `Header`。
  - 修复：citation source/title 使用 normalized substring match；title matching 支持 title/source fallback；重建 KB 时 title 从文件名提取，例如 `07_KB Ingest & Search.md` → `KB Ingest & Search`。
  - 最终 Day28 Hybrid QA20 strict gate：`answer_hit_rate=90.0%`、`citation_hit_rate=100.0%`、`effective_rag_rate=100.0%`、`title_hit_rate=95.0%`、`p95_latency_ms=5921`、`failed=0`、`All regression gates passed!`。
  - 注意：`p95_latency_ms=5921ms` 已接近 `6000ms` 门槛，后续不要无约束增加 rerank 复杂度。



### Day29：KB seed / eval workflow 脚本化

- Day29 已完成 KB seed 与 RAG eval workflow 脚本化，目标是把 Day28-C 暴露出的“live KB 状态影响 QA20 评测”的问题收敛成可复现流程。
- Day29-A：`feat(day29): add kb seed workflow script`
  - 新增：`scripts/seed_kb.py`、`tests/scripts/test_seed_kb.py`。
  - `seed_kb.py` 默认筛选 `docs/kb_seed/01-11`，`source` 保持 `docs/kb_seed/<filename>.md`，`title` 统一从文件名提取。
  - 支持 `--dry-run`、`--reset-runtime --yes`、`--ingest`。
  - 支持输出 `eval/kb_seed_manifest.jsonl`，用于记录本次 seed 的 path/source/title/text_chars/doc_id/chunks。
  - 本地验收：
    - `pytest tests/scripts/test_seed_kb.py -q` → 4 passed
    - `pytest -q` → 61 passed
    - `python scripts/seed_kb.py --dry-run` → 成功筛选 11 个 seed 文档。
- Day29-B：`feat(day29): add rag eval workflow runner`
  - 新增：`scripts/run_rag_eval_workflow.py`、`tests/scripts/test_run_rag_eval_workflow.py`。
  - workflow runner 编排：health check → seed KB → run QA20 eval → build strict report → print summary。
  - `--reset-runtime --yes` 只执行 runtime reset 并退出，提示重启 uvicorn 后再 seed/eval，避免服务进程持有 Chroma 文件时直接删除造成状态不一致。
  - 本地验收：
    - `pytest tests/scripts/test_run_rag_eval_workflow.py -q` → 2 passed
    - `pytest tests/scripts/test_seed_kb.py -q` → 4 passed
    - `pytest -q` → 63 passed
  - CI 已通过。
- Day29-C：`fix(day29): warm up provider before rag eval workflow`
  - 第一次 workflow 实跑时，seed/eval/report 全链路跑通，但 strict gate 因 `p95_latency_ms=6512` 失败。
  - 当时质量指标均正常：`answer_hit_rate=90%`、`citation_hit_rate=100%`、`effective_rag_rate=100%`、`title_hit_rate=95%`、`failed=0`。
  - 定位：QA20 只有 20 条样本，p95 对单个慢请求敏感；本地 Ollama 首次请求/冷启动会把尾延迟顶高。
  - 修复：`run_rag_eval_workflow.py` 在正式 eval 前增加 provider warmup；warmup 调用 `/chat`，`use_kb=false`，`max_tokens=16`，`temperature=0.0`；支持 `--skip-warmup`。
  - warmup 后最终结果：
    - `total=20`
    - `success=20`
    - `failed=0`
    - `answer_hit_rate=0.90`
    - `citation_hit_rate=1.00`
    - `effective_rag_rate=1.00`
    - `title_hit_rate=0.95`
    - `avg_latency_ms=1495`
    - `p50_latency_ms=1396`
    - `p95_latency_ms=2750`
    - `All regression gates passed!`
  - CI 已通过。
- Day29 结论：
  - QA20 不再依赖手工清理 KB 与手工入库命令；
  - seed title/source metadata 稳定；
  - workflow 能自动 seed/eval/report；
  - provider warmup 显著降低 Ollama 首次请求导致的 p95 抖动。


### Day30：v2 收口：系统设计、演示手册、面试讲解稿与最终归档

- Day30 是 `chat-api v2` 的收口日，不新增后端业务功能，重点是把 v2 做成可展示、可讲解、可验收、可归档的阶段版本。
- Day30-A：`docs(day30): complete system design document`
  - 完成 `docs/system_design.md`，从原先的标题骨架补全为完整中文系统设计文档。
  - 覆盖内容：
    - 项目概览；
    - 总体架构；
    - `/chat` 同步请求链路；
    - `/chat/stream` SSE 流式链路；
    - RAG Pipeline；
    - RAGBackend abstraction；
    - native/langchain backend；
    - RAG observability；
    - Hybrid RAG；
    - PromptHub / A/B Compare；
    - Run Log / Replay；
    - Error Handling；
    - QA20 Evaluation / Regression Gates；
    - Design Trade-offs；
    - Current Boundaries and Future Work。
  - 后续修正：将 5.2 之后残留英文段落统一改为中文，保留代码、接口名、字段名和文件名等工程标识。
  - CI 已通过。
- Day30-B：`docs(day30): add v2 demo guide`
  - 新增 `docs/v2_demo_guide.md`。
  - 定位：演示命令手册，不是架构说明。
  - 演示链路：
    - 环境准备；
    - `/health`；
    - `/chat` mock / ollama；
    - `/chat/stream` SSE；
    - reset + seed KB；
    - RAG sync chat；
    - Hybrid RAG metadata；
    - RAG streaming；
    - Prompt Compare；
    - Run Replay；
    - RAG Eval Workflow；
    - Error Demo；
    - 测试与 CI；
    - runtime artifact 清理。
  - 实跑确认：普通 `/chat` ollama 能正常返回，`rag.enabled=false` 是预期，因为该步没有开启 `use_kb=true`。
  - CI 已通过。
- Day30-C：`docs(day30): add interview talk track`
  - 新增 `docs/interview_talk_track.md`。
  - 定位：面试讲解稿，不是命令手册。
  - 覆盖内容：
    - 30 秒 / 1 分钟 / 3 分钟项目介绍；
    - 为什么做这个项目；
    - 系统架构讲法；
    - `/chat` 与 `/chat/stream` 讲法；
    - PromptHub / A/B Compare / Replay；
    - RAG Pipeline；
    - `candidate_k`；
    - RAGBackend abstraction；
    - native/langchain backend；
    - RAG observability；
    - Hybrid RAG；
    - QA20 eval 和 strict gates；
    - Day28 / Day29 真实排障案例；
    - 设计取舍；
    - 项目边界；
    - 面试官常问问题；
    - 2 分钟 / 5 分钟压缩讲稿；
    - 简历 bullet 提炼。
  - CI 已通过。
- Day30-D：最终文档收口
  - 更新 `README.md` 与 `HANDOFF.md`，把 v2 完结状态写清楚。
  - 生成 `Day30.md` 作为本地学习记录。
  - 提交 `README.md` 与 `HANDOFF.md` 后，`chat-api v2-langchain-rag` 阶段正式完结。
- v2 最终验收：
  - `pytest -q` → 63 passed；
  - `run_rag_eval_workflow.py --provider ollama` strict gate 通过；
  - 最新 QA20 结果：
    - `answer_hit_rate=0.90`
    - `citation_hit_rate=1.00`
    - `effective_rag_rate=1.00`
    - `title_hit_rate=0.95`
    - `p95_latency_ms=2750`
    - `failed=0`
- 对话归档说明：
  - 本对话可作为 `chat-api v2` 项目记录归档；
  - 后续在“Agent智能体开发计划”对话中开始第二个 Agent 项目，避免当前长对话继续变慢。

---

## 3. v2-langchain-rag 归档状态（历史基线）

- 当前分支：`v2-langchain-rag`
- v1 主链路仍在 master 稳定可用。
- mock：`/health`、`/chat`、`/chat/stream`、`/demo`、`/prompt/compare`、`/prompts`、`/runs/*`、`/kb/*` 全部 OK。
- ollama：可达时 `/chat`、`/chat/stream`、`/prompt/compare` OK；不可达时 `/chat`=502(detail 结构化)，`/chat/stream`=200 + `event:error`。
- RAG：同步与流式均支持 `use_kb/kb_top_k`；citations 可追溯到 `doc_id/chunk_id/source/title`；Day25 后 `/chat` 与 `/chat/stream` 均通过统一 `RAGBackend` 构建上下文；Day26 后 `native/langchain` 双 backend 均可真实检索；Day27 后暴露 backend/timing observability；Day28 后支持 Hybrid RAG fusion rerank；Day29 后支持可复现 seed/eval/report workflow。
- 评测：`python scripts/eval_qa_rag.py --qa eval/qa_rag_20.jsonl --provider ollama` 可跑完 QA20，并输出 summary；Day29 后推荐使用 `scripts/run_rag_eval_workflow.py` 一键 seed/eval/report。
- 报告：`python scripts/build_eval_report.py ... --strict` 可生成 report，并在当前结果下通过 regression gates。
- 归档测试基线：`pytest -q` 为 63 passed（包含 Day24 backend factory、Day25 route backend 接入、Day26 langchain backend contract、Day27 observability、Day28 hybrid rerank、Day29 workflow tests）。
- CI：master 与 v2 分支均可通过 GitHub Actions；Day26–Day29 相关提交均已通过。
- Demo：`docs/demo_storyline_day22.md` 已经实跑验证；Day30 新增 `docs/v2_demo_guide.md` 作为 v2 演示命令手册。
- 文档：Day30 已完成 `docs/system_design.md`、`docs/v2_demo_guide.md`、`docs/interview_talk_track.md`，可用于系统设计讲解、能力演示与面试表达。
- 项目状态：`chat-api v2-langchain-rag` 阶段正式完结，可归档。

---

## 4. Day19–Day30 重要经验（面试可讲）

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

Day28 的核心不是简单增加规则，而是把检索排序升级为轻量 Hybrid RAG：保留 vector retrieval，引入 lexical scoring，再用 fusion rerank 融合排序，同时通过 route observability 暴露 `retrieval_mode/fusion/vector_weight/lexical_weight`。Day28-C 的排障经验也很关键：评测失败可能来自 live KB 状态或 citation scoring 口径，而不一定是检索算法本身。

Day29 的价值是把评测链路从手工操作升级为可复现 workflow：`seed_kb.py` 固化 seed 文档选择、title/source metadata 与 manifest；`run_rag_eval_workflow.py` 串联 health check、seed、provider warmup、QA20 eval 和 strict report。Day29-C 还验证了本地 Ollama 的冷启动会显著影响 20 样本 p95，provider warmup 能把 p95 从 6512ms 降到 2750ms。

Day30 的价值是把 v2 阶段从“功能完成”整理为“可展示、可讲解、可验收、可归档”：补全中文系统设计文档，新增 v2 演示手册，新增面试讲解稿，并最终更新 README/HANDOFF。

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

## 6. v2-plus 当前状态与下一步

当前分支：`v2-langchain-rag-plus`。

当前定位：`Production-ready LLM Chat Gateway`。

### 已完成

```text
Day2-Day6: Provider / OpenAI-compatible / persistence / history
Day7: UsageRecord and token accounting
Day8: UsageCost and reporting APIs
Day9: API Key authentication and CallerIdentity
```

### 当前 API 边界

```text
Public: /health /ready /docs /redoc /openapi.json /demo
Authentication: /auth/whoami
Protected: /chat /chat/stream /v1/chat/completions /prompt/compare
           /conversations/** /usage/** /kb/** /prompts /runs/**
```

### 当前数据边界

```text
Conversation
Message
UsageRecord
UsageCost
APIKey(id/prefix/key_hash/name/status/created_at/revoked_at)
```

关键不变量：

```text
API Key plaintext 不进入数据库
pepper 不进入数据库或 Git
revoked key 不能认证
CallerIdentity 不含 plaintext/hash
Message 不保存请求级 usage/cost
unknown_price/usage_unavailable 金额为 NULL
```

### Next Work

```text
Chat-Day10: Rate limit / token quota
```

优先复用 `CallerIdentity.key_id`，分离 request limit 与 token quota，明确 429、Retry-After、remaining/reset、流式扣减、并发安全和 Redis 分布式边界。
