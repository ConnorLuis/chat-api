# Chat-Day12 load testing

本目录提供可复现的 HTTP 并发压测，而不是把单次手工请求包装成“性能测试”。压测器覆盖原生与 OpenAI-compatible 的同步/流式路径，并自动输出吞吐量、P50/P95/P99 延迟、错误率和流式 TTFT。

## 1. 固定服务端条件

基准测试不要使用 `--reload`，先固定为单 worker、独立数据库，并关闭会主动拒绝请求的限流和 quota。第一个终端运行：

```bash
cd ~/projects/chat-api

export DATABASE_URL=sqlite:///./data/load_test.db
export EMBEDDING_PROVIDER=mock
export API_AUTH_ENABLED=false
export REQUEST_RATE_LIMIT_ENABLED=false
export TOKEN_QUOTA_ENABLED=false
export APP_LOG_LEVEL=WARNING

python -m src.app.db

python -m uvicorn src.app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1 \
  --log-level warning \
  --no-access-log
```

如果服务启用了 API Key 鉴权，只在运行压测器的终端设置 `CHAT_API_KEY`。报告只记录该环境变量是否存在，不会写入 Key 内容。

## 2. 运行确定性 mock 基线

第二个终端运行：

```bash
cd ~/projects/chat-api

python scripts/run_load_test.py \
  --config benchmarks/configs/mock_baseline.json
```

默认输出目录为：

```text
benchmarks/results/mock-baseline-<UTC timestamp>/
├── report.md
├── summary.json
└── <scenario>.json
```

- `report.md`：面试和代码评审可读的聚合报告。
- `summary.json`：机器可读的场景汇总、环境和 Git commit。
- `<scenario>.json`：该场景的汇总与逐请求原始样本，便于复核长尾和错误。

`benchmarks/results/` 是运行产物，已加入 `.gitignore`。不要把本机生成的大量逐请求数据提交到 Git；README 只摘录最终、可解释的聚合结果。

## 3. 指标和成功语义

| 指标 | 口径 |
|---|---|
| Throughput | 测量请求完成数 / 该场景墙钟时间，单位 req/s |
| Latency | 发出请求前至完整 JSON 或完整 SSE 流消费结束 |
| P50/P95/P99 | 对全部测量请求延迟做线性插值百分位 |
| TTFT | 流式请求首个非空 native `token` 或 OpenAI content delta 的时间 |
| Error rate | 失败数 / 测量请求总数 |

成功不仅要求 HTTP 2xx：同步响应还必须符合对应 JSON 契约；原生流必须收到 `event: done` 和 `[DONE]`；OpenAI-compatible 流必须收到 `data: [DONE]`。SSE `error`、错误 JSON 或流提前结束都计为失败。

每个场景先执行配置中的 warm-up，warm-up 不进入结果。若 warm-up 失败，整个运行立即停止，避免输出看似完整但实际无效的报告。

压测客户端固定 `trust_env=False`，不会意外继承系统 `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`，避免本机回环流量被代理配置改变。

所有场景都会先完成并写出报告；只要测量阶段存在失败请求，CLI 最终返回非零退出码，便于脚本或 CI gate 识别，同时不丢失排障所需的原始样本。

## 4. 可复现规则

正式记录结果时：

1. 固定代码 commit、Python/依赖版本、worker 数、`APP_LOG_LEVEL`、数据库和配置 JSON。
2. 关闭 `--reload`，测试期间不要运行测试套件或其他重负载任务。
3. 使用独立的 `data/load_test.db`，不要压测日常开发数据库。
4. 先运行 mock 基线，验证 Gateway、SSE、usage 持久化和客户端本身。
5. 相同 suite 连续运行 3 次；若波动明显，报告中给出三次范围，不挑最好的一次。
6. 真实模型结果必须注明 CPU/GPU、显存、Ollama 版本和模型精度；不能把单机数字宣称为系统普遍上限。

如果报告出现 `database is locked`，这是 SQLite 单写者在并发 usage 持久化下的真实服务端失败，不能从结果中删除或归因给压测客户端。保留错误率和代表性错误，说明当前 SQLite 适合本地/单机基线；更高写并发应在后续用 PostgreSQL、正式迁移和独立压测重新验证。WAL/busy timeout 可以作为单机调优实验，但不能替代生产数据库边界。

报告自动记录 Python、平台、CPU 数、httpx、Git commit 和工作区是否 dirty。配置中的 `metadata` 用于补充 worker、数据库和硬件说明。

## 5. 可选 Ollama 端到端基线

先确认 `OLLAMA_BASE_URL=http://127.0.0.1:11434`，并将 `ollama_baseline.example.json` 复制为自己的配置，写明真实模型和硬件信息，再运行：

```bash
python scripts/run_load_test.py \
  --config benchmarks/configs/ollama_baseline.example.json
```

Ollama 场景请求量刻意较小，目标是观察模型推理下的吞吐、端到端 P95 和 TTFT；它不能替代 mock 场景对 Gateway 工程开销的测量。

## 6. 自定义输出和服务地址

```bash
python scripts/run_load_test.py \
  --config benchmarks/configs/mock_baseline.json \
  --base-url http://127.0.0.1:8001 \
  --output-dir benchmarks/results/manual-run
```

场景名必须唯一，`concurrency` 不能超过 `requests`。支持的 `mode` 为：

- `native_sync`
- `native_stream`
- `openai_sync`
- `openai_stream`

## 7. Day12 验收

- 压测工具单元测试和全量回归通过。
- mock suite 的全部场景有实际本机结果。
- `report.md` 同时给出 req/s、P50/P95、错误率；流式场景额外给出 TTFT。
- 抽查 `<scenario>.json`，确认请求数、状态码分布和错误分类可复核。
- README/HANDOFF 只摘录真实测量结果，并注明环境、配置和 commit。
