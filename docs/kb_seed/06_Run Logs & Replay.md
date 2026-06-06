# Header
- Title: 06_Run Logs & Replay (JSONL Run Log + Query APIs + CLI Replay)
- Source：kb_seed
- Scope:
  - 只讲：runs/prompt_runs.jsonl 的记录规范、坏行容错、/runs查询接口、replay_compare CLI
  - 不讲：Prompt注入、A/B compare 业务、RAG原理
- Files:
  - 写日志：`src/app/llm/run_logger.py`
  - 回放存储/索引：`src/app/core/run_store.py`
  - 回放路由：`src/app/api/runs/routes_runs.py`
  - compare replay CLI：`scripts/replay_compare.py`
- Run log path:
  - 默认：`runs/prompt_runs.jsonl`
  - 可通过env覆盖：`RUN_LOG_PATH`
- Related Endpoints：
  - `GET /runs/trace/{trace_id}`
  - `GET /runs/compare/{compare_group_id}`
- Related Tests：
  - `tests/runs/test_run_log_writing.py`
  - `tests/runs/test_runs_trace_get.py`
  - `tests/runs/test_runs_compare_get.py`
# TL;DR
- 每次LLM调用都会落盘一条JSONL run record（一行一个JSON），作为可审计、可回放证据。
- 回放支持两条路径：trace_id回放单次调用，按`compare_group_id`聚合A/B对比。
- 读取JSONL时允许出现坏行（bad_lines）, 接口仍返回可用记录并给出warning。
# Why Run Logs
- Debug：trace_id 对齐日志、复盘 prompt/version/ 参数
- Repro：不是保证答案一致，而是保证 “证据链完整”
- Eval：评测脚本可直接复用运行日志字段，统计耗时、输出规模与引用数据
- Experiment：关联 compare_group_id，为 A/B 对照实验提供真实原始调用数据
- Collaborate：统一日志规范，团队成员可快速查阅历史记录，降低协作成本
- Audit：完整留存调用链路信息，满足线上溯源、合规审计的硬性要求
# Run Record Schema（最小字段集合 + 模式差异）
## Common fields
- `trace_id`
- `mode`：`chat | stream | compare`
- `provider, model`
- `prompt_id, prompt_version`
- `latency_ms`
- `prompt_chars, output_chars`
- `temperature, top_p, max_tokens`
## Stream-specific fields
- token_events(事件计数，不等于tokenizer token数)
- （可选）rag_*（如 rag_enabled/rag_hits/context_chars/citations_count/rag_error）
## Compare-specific fields
- `compare_group_id`
- `variant`：`A | B`
# Write semantics（写入语义与并发假设）
- 写入策略：append-only（一行一条）
- 是否 best-effort：写失败不影响主流程（你项目一贯风格）
- 并发：多请求同时写入的风险与现实策略
  - 现实可接受：单机开发/面试演示
  - 未来可选：文件锁/队列/改成 SQLite
# Read semantics（读取语义：bad_lines / incomplete records）
- bad_lines：解析失败的行数（无效 JSON、半行）
- 对回放接口的影响：
  - 仍返回成功解析的 records
  - 返回 warning（如 “记录不完整”）
- Compare 回放的“不完整”：
  - 期望 A/B 两条
  - 若只找到 1 条：返回 records_count=1 + warning（脚本也提示）。仍返回 已有记录（A 或 B），并在 warning 里说明缺失哪个 variant（如缺 B）。
# Replay APIs Contract
## GET /runs/trace/{trace_id}
- 200：records: [...]（可能 1 条或多条）
- 404：找不到则 404
- 选择 404 的原因：`trace_id` 是精确查询键，不是列表过滤条件；如果不存在，语义上就是 not found，而不是空列表。
- 返回结构：
  - trace_id
  - records：[...]
  - bad_lines
  - metadata.trace_id/latency
  - (可选)warning
## GET /runs/compare/{compare_group_id}
- 200：返回 A/B 两条（按 A/B 排序）
- summary：latency_diff / output_diff
- 不完整：records_count < 2 时仍 200 + warning
- bad_lines：记录错误行数
# CLI Replay（scripts/replay_compare.py 的语义）
- 调用：python scripts/replay_compare.py <compare_group_id> --log runs/prompt_runs.jsonl
- 输出包含：
  - A/B 两条的 prompt/version、latency、output_chars、参数
  - 最后 summary（哪个更快/更长）
- 破坏实验：删掉 B → 输出“不完整警告”
# Pitfalls & Debug Playbook
- runs.jsonl 出现坏行（bad_lines > 0） 
- compare_group_id 缺失 → /runs/compare 无法聚合；属于“不完整记录”，不是 bad_lines。
- 记录只有 A 没 B（破坏实验），保持200输出单个记录，加一个warning
- RUN_LOG_PATH 指错/权限不足导致不落盘
- prompt_id/version=none 的降级记录，则不适用prompt_id
- stream token_events 与 tokenizer token 不一致
- trace_id 不是唯一？那么返回list
- JSONL 文件过大：读取策略（只读最近 N 条/未来优化）
# Tests Mapping
- test_run_log_writing.py：chat/stream 都写入一条 run record（字段完整）
- test_runs_trace_get.py：trace 找不到 404；找到字段完整
- test_runs_compare_get.py：compare 回放 A/B 排序 + summary + bad_lines 容错
- （可选）破坏实验测试：bad line 注入后 bad_lines > 0 仍 200
---
# Keywords
runs/prompt_runs.jsonl, JSONL, trace_id, compare_group_id, variant, mode, bad_lines, warning, replay, /runs/trace, /runs/compare, RUN_LOG_PATH, append-only

# QA Seeds
{"qid": "q001", "question": "为什么回放不保证答案一致？保证的是什么？", "expected_keywords": ["回放", "答案不一致", "模型随机性", "动态环境", "prompt版本", "入参", "证据链", "链路还原", "现场复现"], "min_hits": 2, "expected_sources": ["Run Logs & Replay"], "note": "考察回放功能的固有局限、底层原因，以及该功能真正保障的核心目标"} 
{"qid": "q002", "question": "bad_lines 的容错策略是什么？为什么接口仍返回 200？", "expected_keywords": ["bad_lines", "脏数据", "异常行", "容错策略", "降级处理", "HTTP 200", "链路不中断", "异常捕获", "业务隔离"], "min_hits": 2, "expected_sources": ["Run Logs & Replay"], "note": "考察脏数据行的容错处理方案，以及接口维持200状态码的契约设计思路"}
{"qid": "q003", "question": "compare 回放缺 B 时应该怎么处理？", "expected_keywords": ["compare", "A/B实验", "回放", "分组B缺失", "数据补空", "异常标记", "告警提示", "完整性校验"], "min_hits": 2, "expected_sources": ["Run Logs & Replay"], "note": "考察A/B对比回放场景下，实验组B数据缺失时的标准处理逻辑"}
