# Header

* Title：12_RAG Eval Report & Regression Gates（Evaluation Report + Quality Gates + Regression Safety）
* Source：kb_seed
* Scope：

  * RAG 离线评测报告
  * QA20 评测结果解释
  * regression gates 回归门槛
  * strict 模式失败退出
  * report.md 面试展示材料
* Out of scope：

  * KB 入库与 Chroma 细节（见 07）
  * RAG 注入与 citations 细节（见 08）
  * rerank / candidate_k 细节（见 13）
* Files：

  * `scripts/eval_qa_rag.py`
  * `scripts/build_eval_report.py`
  * `eval/qa_rag_20.jsonl`
  * `eval/results/rag_eval_20.jsonl`
  * `eval/results/rag_eval_20_summary.json`
  * `eval/reports/rag_eval_report.md`
* Related Tests：

  * `tests/eval/test_eval_metrics_unit.py`

# TL;DR

* Day19 产出了 RAG QA20 离线评测结果，Day20 将结果整理成可读报告。
* `eval_qa_rag.py` 负责调用 `/chat`、计算逐题指标、输出 results.jsonl 和 summary.json。
* `build_eval_report.py` 负责读取结果、生成 markdown 报告，并根据 regression gates 判断是否通过。
* 回归门槛不追求 100%，而是保证核心能力不退化：answer、citation、effective_rag、title_hit、latency、failed_count。
* strict 模式下，只要任一核心门槛失败，脚本应 `exit 1`，用于后续 CI 或手工回归检查。

# Why RAG Evaluation Report

RAG 功能是否可用，不能只靠人工肉眼测试。

需要一套最小但稳定的离线评测来回答：

* 检索是否真的发生？
* context 是否真的注入？
* citations 是否可追溯？
* 模型回答是否覆盖关键事实？
* latency 是否在可接受范围？
* 改动 Prompt、KB 或 rerank 后是否造成退化？

因此，Day20 引入 `rag_eval_report.md`，把离线评测结果从“控制台输出”升级为“可展示、可审计、可回归”的工程证据。

# Evaluation Inputs

## qa_rag_20.jsonl

`eval/qa_rag_20.jsonl` 是评测集，每行一个 JSON 对象。

核心字段：

* `qid`：题目编号，例如 `q019`。
* `question`：用户问题。
* `expected_keywords`：期望回答中出现的关键词或同义表达。
* `min_hits`：最少命中关键词数量。
* `expected_sources`：期望 citation source，例如 `kb_seed`。
* `expected_titles`：期望 citation title，例如 `RAG in Chat/Stream`。
* `note`：该题考察点说明。

设计原则：

* question 要包含可召回的强锚点词。
* expected_keywords 不应过窄，允许中英文同义词。
* expected_titles 是诊断项，不一定考察点说明。

作为核心通过条件。

* 评测集应覆盖 KB Seed 的主要主题，而不是只考一篇文档。

# Evaluation Outputs

## results.jsonl

`eval/results/rag_eval_20.jsonl` 是逐题结果，每行一题。

核心字段：

* `qid`
* `question`
* `trace_id`
* `answer`
* `http_code`
* `latency_ms`
* `provider`
* `model`
* `prompt_id`
* `prompt_version`
* `rag`
* `context_chars`
* `citations`
* `answer_score`
* `citation_score`
* `effective_rag`
* `error`
* `note`

用途：

* 定位失败题。
* 回放单题 trace。
* 对比修改前后 answer/citation/latency。
* 为 report.md 提供明细数据。

## summary.json

`eval/results/rag_eval_20_summary.json` 是汇总指标。

核心字段：

* `total`
* `success`
* `failed`
* `answer_hit_rate`
* `citation_hit_rate`
* `effective_rag_rate`
* `title_hit_rate`
* `avg_latency_ms`
* `p50_latency_ms`
* `p95_latency_ms`
* `latency_samples`
* `failures`

用途：

* 快速判断整轮评测是否达标。
* 作为 regression gates 的输入。
* 在 README / 面试材料中展示核心结果。

# Metrics Contract

## answer_hit

`answer_hit` 表示回答是否覆盖关键事实。

规则：

* 对 answer 做 normalize。
* expected_keywords 采用子串匹配。
* 命中关键词数量 `hits_count >= min_hits`。
* 如果回答包含 uncertain 模板，则即使命中关键词也不能算通过。

uncertain 模板包括：

* `不确定/需要更多上下文`
* `无法基于现有资料回答`
* `文档中未提供`
* `资料中没有提供`
* `无法直接回答`

为什么需要 uncertain guard：

模型有时会说“文档中没有 candidate_k 信息”，这句话本身包含 `candidate_k`，如果只做关键词匹配，会造成假阳性。

## citation_hit

`citation_hit` 表示回答是否带有可追溯引用。

当前规则：

* `citations` 非空。
* 至少一个 citation 的 `source` 命中 expected_sources。

原因：

* 同一个问题可能由多篇文档共同回答。
* title 严格匹配容易造成假阴性。
* source 命中更适合作为核心引用通过条件。

## title_hit

`title_hit` 是诊断项。

规则：

* 至少一个 citation 的 `title` 命中 expected_titles。

用途：

* 判断是否召回了预期文档。
* 辅助定位 rerank 或 KB 文档锚点问题。
* 不建议作为唯一通过标准。

## effective_rag

`effective_rag` 表示 RAG 是否真的生效。

规则：

* `rag.enabled == true`
* `rag.hits > 0`
* `context_chars > 0`

如果这三个条件不满足，说明请求可能没有真正使用 KB context。

## latency

latency 直接来自 `/chat` 返回的 `metadata.latency_ms`。

summary 中统计：

* average latency
* p50 latency
* p95 latency

p95 小样本时不应输出假 0，而应使用可解释算法或输出 null。

# Regression Gates

`build_eval_report.py` 支持 strict gate。

推荐门槛：

* `answer_hit_rate >= 0.90`
* `citation_hit_rate >= 0.95`
* `effective_rag_rate >= 0.95`
* `title_hit_rate >= 0.85`
* `p95_latency_ms <= 6000`
* `failed_count == 0`

为什么不追求 100%：

* LLM 表达存在波动。
* 关键词粗评有天然局限。
* 某些 title_hit 失败不代表 RAG 链路失败。
* 过度追求 100% 容易导致评测集过拟合。

因此，门槛应保证核心能力稳定，而不是强行把测试集调满分。

# Report Generation

生成报告命令：

```bash
python scripts/build_eval_report.py \
  --results eval/results/rag_eval_20.jsonl \
  --summary eval/results/rag_eval_20_summary.json \
  --out eval/reports/rag_eval_report.md \
  --strict
```

成功输出：

```text
Report generated: eval/reports/rag_eval_report.md
All regression gates passed!
```

报告包含：

* Summary
* Regression Gates
* Per-question Results
* Failed / Weak Cases
* Engineering Notes

# Final Day19 / Day20 Result

当前 QA20 结果：

* total：20
* success：20
* failed：0
* answer_hit_rate：95%
* citation_hit_rate：100%
* effective_rag_rate：100%
* title_hit_rate：95%
* p95_latency_ms：低于 6000ms gate
* strict gate：PASS

这个结果说明：

* `/chat` RAG 主链路稳定。
* citations 可追溯。
* KB Seed 清洗有效。
* query-aware rerank 没有明显退化。
* report 可作为面试展示材料。

# Failure Modes

## report 生成失败

可能原因：

* results.jsonl 不是合法 JSONL。
* summary.json 不存在。
* 输出目录不存在且脚本没有创建。
* results 每行没有 `answer_score` / `citation_score` 字段。

## strict gate 失败

可能原因：

* answer_hit_rate 低于门槛。
* citation_hit_rate 低于门槛。
* effective_rag_rate 低于门槛。
* p95 latency 超过门槛。
* failed_count 不为 0。

## title_hit_rate 下降

可能原因：

* KB 文档 title 修改。
* expected_titles 过窄。
* rerank 没有把目标文档排进 top_k。
* KB Seed 新增文档引入了召回竞争。

# Tests Mapping

* `tests/eval/test_eval_metrics_unit.py`

  * 验证关键词命中。
  * 验证 uncertain answer guard。
  * 验证 citation_hit/source_hit/title_hit 分层口径。
* `tests/kb/test_rag_rerank.py`

  * 验证 query-aware rerank 不会无条件偏向某篇文档。
* `tests/kb/test_index_text.py`

  * 验证 KB Seed 截断规则，防止 Keywords / QA Seeds 污染。

# Pitfalls & Debug Playbook

## answer_hit 低，但 citation_hit 高

说明检索链路通常没问题，优先检查：

* expected_keywords 是否过窄。
* 回答是否使用了同义表达。
* KB 正文是否缺少明确结论。
* prompt 是否过于保守导致 uncertain answer。

## citation_hit 高，但 title_hit 低

说明 source 命中，但预期文档不稳定。

排查：

* expected_titles 是否太严格。
* query 是否缺少强锚点。
* 是否需要调整 query-aware rerank。
* 是否新增了主题相近的 KB 文档。

## effective_rag 低

优先检查：

* use_kb 是否为 true。
* KB 是否为空。
* Chroma 是否正常。
* rag.hits 是否大于 0。
* context_chars 是否大于 0。

---

# Keywords

rag evaluation
eval report
regression gate
strict mode
answer_hit
citation_hit
title_hit
effective_rag
p95 latency
qa_rag_20
results.jsonl
summary.json

# QA Seeds

Q: RAG Eval Report 的作用是什么？
A: 把离线评测结果整理成可展示、可审计、可回归的 markdown 报告。

Q: strict gate 的作用是什么？
A: 当 answer_hit_rate、citation_hit_rate、effective_rag_rate、latency 或 failed_count 等指标低于门槛时，让脚本退出失败，防止回归。

Q: 为什么 title_hit 不作为唯一通过标准？
A: 因为同一问题可能由多篇文档回答，title 严格匹配容易误判；title_hit 更适合作为诊断项。

Q: 为什么 answer_hit 需要 uncertain guard？
A: 因为模型可能在“无法回答”的句子里包含 expected keywords，单纯关键词匹配会造成假阳性。
