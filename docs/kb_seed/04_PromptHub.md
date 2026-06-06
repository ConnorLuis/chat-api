# Header
- Title：04_PromptHub（Prompt Registry + Versioning + Run Log + Replay）
- Source：kb_seed
- Scope：只讲 **prompt_id/version/vars → system 注入 → 记录 run → 回放/对比**
	- 不讲 SSE 协议（在 03）
	- 不讲 KB/chroma（在 07/08/09）
- Files：
	- Prompt 注册/渲染：`src/app/llm/prompt_registry.py`
	- Run log 落盘：`src/app/llm/run_logger.py`
	- Chat 路由使用点：`src/app/api/routes_chat.py`
	- Compare 路由：`src/app/api/prompt/routes_prompt.py`
- Prompts Dir：`prompts/<prompt_id>/<version>.md`
- Run Log：`runs/prompt_runs.jsonl`
- Related Endpoints：
    - `GET /prompts`
    - `POST /chat`（使用 prompt_id/version）
    - `POST /chat/stream`（meta/usage 含 prompt_id/version）
    - `POST /prompt/compare`
    - `GET /runs/trace/{trace_id}`
    - `GET /runs/compare/{compare_group_id}`
- Related Tests（列 6 个即可）：
    - `tests/chat/test_chat_prompt_registry.py`
    - `tests/runs/test_run_log_writing.py`
    - `tests/prompt/test_prompts_list.py`
    - `tests/prompt/test_prompt_compare_contract.py`
    - `tests/runs/test_runs_trace_get.py`
    - `tests/runs/test_runs_compare_get.py`
# TL;DR
- PromptHub 用 `prompt_id + prompt_version` 让提示词**可版本化、可复现**，并通过 `prompt_vars` 渲染模板。
- Prompt 会被注入为 **system message**，再与用户 messages 一起送入 LLM；调用过程被写入 `runs/prompt_runs.jsonl`。
- 对同一输入可做 **A/B Prompt Compare**（compare_group_id），并可按 `trace_id` 或 `compare_group_id` 回放与对比。
# Why PromptHub
- Prompt 不是字符串，是“可迭代资产”
- 版本化：线上/面试都能说清楚“我用的是 chat@v1”
- 可回放：出了问题能追溯“当时提示词版本 + 变量 + 参数”
- 可对比：A/B 让提示词优化有证据（latency/长度/引用）
- 统一集中托管，解决提示词碎片化问题，实现团队资产共享与协作规范。
- 标准化资产形态，可无缝对接对话、RAG 等业务模块，降低业务接入成本。
# Data Model
## Prompt Registry Keys
- `prompt_id`：模板族（如 `chat` / `qa_strict`）
- `prompt_version`：版本（如 `v1`）
- `prompt_vars`：模板变量（dict，可能为空）
## Prompt Render Output
- `system_text`：渲染后的完整提示词文本
- `prompt_chars`：提示词长度（字符数，评测用）
## Run Log Record
- `trace_id`, `mode`（chat/stream/compare）
- `provider`, `model`
- `prompt_id`, `prompt_version`
- `temperature/top_p/max_tokens`
- `latency_ms`
- `prompt_chars`, `output_chars`
- compare 时额外：`compare_group_id`, `variant=A|B`
# Prompt Injection
- 规则 1：如果传 `prompt_id + prompt_version`  
    → 从 `prompts/<id>/<version>.md` 读模板 → 用 `prompt_vars` 渲染 → 作为 **system message** 插入到 messages 开头
- 规则 2：prompt 不存在/渲染失败 → **降级**（不注入 prompt），同时：
	- run log 里记录 `prompt_error`
	- metadata 里 `prompt_id/prompt_version` 变成 `"none"` 或仍回显原值并加 `prompt_error`
- 规则 3：如果用户 messages 已含 system  
    → “优先使用 PromptHub system，用户 system 仍保留但放后面”。最终 messages 顺序：`[PromptHub system] + 原 messages（保持原顺序）`（即用户 system 会排在 PromptHub system 之后）。
# A/B Compare 与 Replay 的关系
## Compare 的输入
- 一次 compare 请求 = 同一 user messages + 两套 prompt（A/B）
- 每套 prompt 产生一条 run log（variant=A/B）
- 这两条 run log 共享 `compare_group_id`
## Compare 的输出指标
- `latency_ms_a/b`、`diff_latency_ms`
- `output_chars_a/b`、`output_chars_diff`
- （可扩展）如果 RAG 开启：citations_count、source_hit 等
## Replay 的两条路径
- `GET /runs/trace/{trace_id}`：回放“单次调用”
- `GET /runs/compare/{compare_group_id}`：回放“一组 A/B”
    - 返回 A/B 两条记录（按 A/B 排序）
    - 返回 summary（latency/长度差）
强调：**回放不是“结果一定完全一样”**（除非 temperature=0 且模型 deterministic）  
回放的目标是：**可追溯、可审计、可解释**（prompt/version/vars/参数/耗时/输出规模）。
灰度：A/B compare 是灰度实验最小模型（同流量对比两策略）, 这里只做同输入双策略对比，不涉及线上分流/发布系统.
# Failure Modes
- prompt 文件不存在（id/version 错）→ 降级 + 记录 prompt_error
- vars 缺少必要键（模板渲染失败）→ 降级 + 记录 prompt_error
- run log 写入失败（IO/权限）→ **best-effort：不影响 /chat 与 /chat/stream 响应**；服务端记录 error 日志（可选：metadata/run 记录 `run_log_error`）
- compare 缺 A/B 其中之一 → `/runs/compare` 返回 `records_count + warning + bad_lines`（并按 A/B 排序尽量返回已有记录）
# Tests Mapping
- `test_chat_prompt_registry.py`：/chat 传 prompt_id/version → metadata 必回显 prompt_id/version；并写入 runs
- `test_stream_meta_has_prompt.py`：stream meta 必含 prompt_id/version
- `test_run_log_writing.py`：chat/stream 都会写 run log（字段完整）
- `test_prompt_compare_contract.py`：/prompt/compare 返回 compare_group_id + A/B metadata；runs 含 compare_group_id
- `test_prompts_list.py`：/prompts 能列出 prompt_id 与 versions
- `test_runs_trace_get.py`、`test_runs_compare_get.py`：回放接口字段完整 + bad_lines 容错
# Pitfalls & Debug Playbook
- prompt_version 传了但 prompt_id 没传 → `prompt_version` 有但 `prompt_id` 无 → 忽略 version，视为不使用 PromptHub（prompt_id/version=none），并记录 warning
- 模板里变量名不一致 → 渲染失败
- Windows/WSL 换行 CRLF 导致 diff/长度统计差异
- runs.jsonl 出现坏行 → 回放接口 bad_lines 处理
- compare_group_id 缺一条（破坏实验删 B）→ replay_compare 脚本输出“不完整警告”
---
# Keywords
prompt_id, prompt_version, prompt_vars, system message, render, template, prompts/, runs/prompt_runs.jsonl, trace_id, compare_group_id, variant, replay, /prompts, /runs/trace, /runs/compare, prompt_error, run_log_error

# QA Seeds
{"qid":"q001","question":"为什么要版本化 prompt？","expected_keywords":["版本化","prompt","追溯","回放","A/B对比","资产管控","故障排查","线上规范"],"min_hits":2,"expected_sources":["PromptHub"],"note":"考察提示词版本化的设计目的、业务价值与工程意义"}
{"qid":"q002","question":"Compare 的 compare_group_id 如何支持回放？","expected_keywords":["compare_group_id","A/B对比","分组标识","回放","数据关联","版本追溯","实验分组"],"min_hits":2,"expected_sources":["PromptHub"],"note":"考察对比分组ID的作用，以及该字段对接回放能力的设计逻辑"}
{"qid":"q003","question":"prompt_vars 渲染失败时应该怎么处理？","expected_keywords":["prompt_vars","变量渲染","渲染失败","异常捕获","降级策略","错误上报","容错处理"],"min_hits":2,"expected_sources":["PromptHub"],"note":"考察提示词变量渲染异常场景下的容错设计与处理方案"}