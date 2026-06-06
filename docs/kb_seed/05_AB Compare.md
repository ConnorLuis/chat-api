# Header
- Title：05_A/B Compare(Prompt Compare + Metrics + Replay Evidence)
- Source：kb_seed
- Scope: 只覆盖`POST /prompt/compare`的输入输出、指标计算、run log证据与回放
  - 不讲PromptHub的目录结构
  - 不讲runs查询API细节
- Files：
  - Compare路由：`src/app/api/prompt/routes_prompt.py`
  - Prompt注入：`src/app/llm/prompt_registry.py`
  - run log：`src/app/llm/run_logger.py`
  - demo：`src/app/api/routes_demo.py`
  - scripts：`scripts/replay_compare.py`
- Related Endpoints：
  - POST /prompt/compare
  - GET /runs/compare/{compare_group_id}
  - （可选）GET /runs/trace/{trace_id}
- Related Tests（列 3–6 个）：
  - tests/prompt/test_prompt_compare_contract.py
  - tests/runs/test_runs_compare_get.py
  - tests/demo/test_demo_page.py
# TL;DR
- A/B Compare 用同一输入 + 两套 Prompt（A/B）跑两次模型，返回并列结果与差异指标。
- 两次调用共享 compare_group_id，并把 A/B 各自的 run log 落盘（可审计可回放）。
- 回放可以按 compare_group_id 聚合出 A/B 两条记录 + summary，用于提示词迭代的证据闭环。
# Why A/B Compare
- Prompt 调优摒弃主观经验
  - 现阶段对比：latency_ms、output_chars
  - 可扩展：如果 compare 开启 RAG，可加入 citations_count / source_hit / answer_hit
- compare_group_id 作为独立实验单元，实现实验流量与数据的精准分组隔离。 
- 结合运行日志与回放能力，让完整实验过程可追溯、可复盘、可跨团队共享。 
- 全程以客观数据为依据，让每一轮提示词优化都具备可采信的实证支撑。 
- 支持多版本并行对照，在线上灰度发布阶段有效降低版本迭代的试错风险。 
  - 这里是实验对比能力，不包含线上分流发布系统。
- 若出现效果异常，可依托分组数据横向比对，快速定位版本差异与问题根因。 
- 沉淀各版本实验基线，把经过验证的优质方案固化为可复用的提示词资产。 
- 统一标准化的实验流程，规范团队迭代动作，避免调优动作碎片化、无章法。
# Request Contract
## CompareRequest
- provider
- messages
## CompareRequest A/B Prompt Spec
- prompt_a：prompt_id, prompt_version, prompt_vars（可选） 
- prompt_b：prompt_id, prompt_version, prompt_vars（可选） 
## 可选参数（采样参数）
- max_tokens, temperature, top_p
- （可选）未来扩展：use_kb/kb_top_k
# Response Contract
## CompareResponse 顶层
- compare_group_id（必有，非空）
- a、b（两个子结果）
- metrics（差异指标对象）
## VariantResult(a/b)
- trace_id（通常 A/B 各自生成 trace_id）
- answer
- metadata 必含：
  - provider, model, latency_ms
  - prompt_id, prompt_version
  - （可选）如果开启 rag：rag（enabled/top_k/hits/context_chars/citations/error）
## Metrics
latency_ms_a, latency_ms_b, diff_latency_ms
output_chars_a, output_chars_b, output_chars_diff
# Evidence: Run Log & Replay
## 为什么 compare_group_id 是证据核心
- 一次 compare 对应两条 run log
- 两条共享 compare_group_id，并带 variant=A/B
- run log 里还要记录采样参数（temp/top_p/max_tokens），否则无法解释差异
## compare run log 最小字段集合
- compare_group_id
- variant（A/B）
- trace_id
- mode="compare"
- provider/model
- prompt_id/prompt_version
- latency_ms
- prompt_chars, output_chars
- temperature/top_p/max_tokens
## 回放路径
- API 回放：GET /runs/compare/{compare_group_id} → A/B 两条 + summary + bad_lines
- CLI 回放：python scripts/replay_compare.py <group_id> --log runs/prompt_runs.jsonl

强调：回放不保证答案完全一致（除非 temperature=0 + deterministic），回放保证的是“证据链完整”。
# Failure Modes
- prompt 文件不存在 / 渲染失败 → 降级为 prompt_id/prompt_version=none 并记录 prompt_error：
  - 对 compare：A/B 各自降级为 none，并记录 prompt_error
- compare 只拿到一条记录（破坏实验删了 B）：
  - replay 脚本输出“不完整警告”
  - /runs/compare 返回 records_count=1 + warning
- runs.jsonl 坏行：bad_lines > 0 但仍返回可用记录 
- provider 不可达：任一变体失败 → compare 整体返回 502（detail 结构化）
# Tests Mapping
- test_prompt_compare_contract.py
  - compare_group_id 非空
  - a/b 必含 metadata(provider/model/latency/prompt_id/version)
  - metrics 字段存在
- test_runs_compare_get.py
  - /runs/compare 返回 A/B 排序 + summary
  - bad_lines 容错（可选：破坏实验）
- （可选）demo 页面：出现 compare UI 关键字
# Pitfalls & Debug Playbook
- curl 复制带 \n → host n 
- compare_group_id 注释/缺失导致回放无法聚合
- 把 B 从 jsonl 删掉 → 回放只剩 A（脚本警告）
- runs.jsonl 坏行 → bad_lines 计数
- prompt_vars 未传/缺失 key → 渲染失败（降级）
- temp/top_p 不同导致答案差异不可解释（要记录）
---
# Keywords
/prompt/compare, compare_group_id, variant, mode=compare, metrics, latency_ms, output_chars, prompt_id, prompt_version, prompt_vars, runs/prompt_runs.jsonl, replay_compare.py, /runs/compare, bad_lines, latency_ms_a, output_chars_diff
# QA Seeds
{"qid": "q001", "question": "compare_group_id 为什么重要？", "expected_keywords": ["compare_group_id", "实验单元", "分组隔离", "流量划分", "A/B对照", "样本对齐", "数据区分"], "min_hits": 2, "expected_sources": ["A/B Compare"], "note": "考察 compare_group_id 在A/B实验中的设计作用、分组逻辑与核心必要性"}
{"qid": "q002", "question": "A/B 的 metrics 计算怎么做、有什么局限？", "expected_keywords": ["metrics", "指标计算", "latency", "引用率", "命中率", "文本长度", "样本偏差", "流量倾斜", "时序干扰"], "min_hits": 2, "expected_sources": ["A/B Compare"], "note": "考察A/B实验量化指标的统计方式，以及指标体系存在的客观局限性"}
{"qid": "q003", "question": "为什么回放不保证答案一致？如何保证可解释？", "expected_keywords": ["回放", "答案不一致", "模型随机性", "动态变量", "环境差异", "版本锁定", "日志溯源", "链路追踪", "可解释性"], "min_hits": 2, "expected_sources": ["A/B Compare"], "note": "考察回放结果无法完全一致的根因，以及保障实验与调用链路可解释的配套方案"}
# Appendix
- compare_group_id: <uuid>
- a.trace_id: <trace_id_a>
- a.metadata: {provider, model, latency_ms, prompt_id, prompt_version}
- b.trace_id: <trace_id_b>
- b.metadata: {provider, model, latency_ms, prompt_id, prompt_version}
- metrics.latency_ms_a|b|diff_latency_ms=latency_ms_a - latency_ms_b: <int>
- metrics.output_chars_a|b|output_chars_diff: <int>