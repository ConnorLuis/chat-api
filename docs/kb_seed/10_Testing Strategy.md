# Header
- Title：10_Testing Strategy（Contract Tests + Isolation + Regression Safety）
- Source：kb_seed
- Scope：只讲测试体系设计与验收策略（不讲业务实现细节）
- Out of scope：CI/部署（后面可选 Day22+）
- Test runner：pytest
- Related files：
  - tests/conftest.py（sys.path 注入）
  - tests 分目录结构（chat/stream/kb/prompt/runs/core/demo）
# TL;DR
- 测试体系以契约测试为核心：锁死输入输出形状、错误语义、SSE 事件顺序，保证重构不回归。
- 用 tmp_path + monkeypatch 做环境隔离：KB、Chroma、runs.jsonl 都在临时目录中运行，避免污染。
- 破坏性实验（坏行/缺 B/断网）被固化为测试用例，确保系统在异常下仍“可解释、可观测、可降级”。
# Test Philosophy
- Contract tests（主力）：校验字段存在、事件顺序、状态码与事件语义严格不变
- Scenario tests（辅助）：验证 Demo 页可用、Mock 引擎正常、RAG 开关按预期生效
- Regression tests（结果）：将历史故障（bad_lines、meta 空块、compare 缺 B）固化为用例
- 核心原则：不测 “答案语义是否正确”（Mock 环境下无法验证），只保接口行为与证据链合规
- 守护 SSE 流式契约：事件块格式、分隔符、payload 结构全程符合标准不紊乱
- 保障 RAG 链路可信：检索字段、引用溯源、上下文预算、降级逻辑按约定执行
- 锁定异常容错行为：脏数据、渲染失败、KB 异常等场景按策略降级不中断服务
- 保证实验与回放链路完整：compare 分组、运行日志、回放溯源全程可核验
- 支撑安全迭代：任何代码修改不破坏既有契约、业务场景与历史故障防护
# Test Layout
- tests/core/*：健康检查、SSE 格式基础（event/data/空行分隔）
- tests/chat/*：/chat 成功契约、错误 502 detail、PromptHub、RAG
- tests/stream/*：SSE 顺序契约、stream error 契约、stream RAG 契约
- tests/kb/*：ingest/search 契约、documents list/delete 契约
- tests/prompt/*：/prompts 列表、/prompt/compare 契约
- tests/runs/*：/runs/trace、/runs/compare、bad_lines 容错
- tests/demo/*：/demo 页面关键字存在（演示台不回归）
# “What is locked” Invariants
## Chat（sync）不变量
- provider=mock 必须 200，且 response 必含 trace_id/answer/metadata
- provider=ollama 不可达 → 502，且 detail 为结构化 JSON（字段完整）
## Stream（SSE）不变量
- Content-Type: text/event-stream
- 第一条事件必须是 meta
- 成功序列：meta → token* → usage → done（done data=[DONE]）
- 异常：HTTP 仍 200，但必须出现 event:error（结构化 JSON）
- RAG 开启：meta/usage/error 必带 rag 摘要；citations 在 usage 中
## PromptHub / Compare / Runs
- prompt_id/version 回显在 metadata（sync）与 meta/usage（stream）
- compare 必返回 compare_group_id，runs 里 A/B 两条共享该 id
- /runs/compare 必支持 bad_lines 容错与“不完整记录 warning”
## KB
- ingest 返回 doc_id，search 能命中并返回 hits 结构
- documents list 支持分页/include_deleted
- delete 会标记 tombstone + 尽量清理向量/文件
# Isolation Strategy
目标：每个测试用例都在“自己的沙箱”里运行，避免真实磁盘/真实向量库/真实日志文件互相污染，保证测试可复现、可并行、可回归。
## 核心手段
- tmp_path：pytest 提供的临时目录（每个 test 都是新的路径），用于隔离：
  - KB_DIR（docs 目录、docs.jsonl、seed 文档等）
  - KB_CHROMA_DIR（Chroma 持久化目录）
  - RUN_LOG_PATH（runs JSONL 日志）
- monkeypatch.setenv：在单个测试生命周期内覆盖环境变量，让应用读取到 tmp_path 下的隔离路径；测试结束后自动回滚，不污染全局 shell 环境。
- `isolated_kb_env`（可选 fixture 名）：把 `tmp_path` 与 `monkeypatch.setenv` 封装成统一测试夹具，一次性隔离 `KB_DIR`、`KB_CHROMA_DIR`、`RUN_LOG_PATH` 等路径，减少每个测试重复配置。
## 关键 env
- KB_DIR：知识库根目录（通常包含 docs/ 与 docs.jsonl），测试里应指向 tmp_path/...，避免写到仓库真实目录。
- KB_CHROMA_DIR：Chroma persist dir（建议默认由 KB_DIR/chroma 拼出），测试里同样指向 tmp_path/.../chroma。
- RUN_LOG_PATH：运行日志 JSONL（例如 runs/prompt_runs.jsonl），测试里应指向 tmp_path/.../runs.jsonl，避免污染真实 runs。
- OLLAMA_BASE_URL：用于“故障注入”；把它指向不可达地址来锁死 /chat 的 502 结构化错误，以及 /chat/stream 的 event:error 契约。
## 为什么不直接用真实磁盘目录
- 会污染仓库：docs.jsonl / chroma 数据 / runs.jsonl 会越跑越大，导致“本地通过、CI 或别人机器不通过”
- 不可复现：测试顺序不同、历史数据残留不同，会导致搜索命中/数量不稳定
- 难并行：多个测试同时写同一目录，容易互相踩踏
# Coverage Boundaries
- 不测模型答案正确性（mock/随机性）
- 不测性能基准（Day19 eval 才做粗统计）
- 不测并发写一致性（当前阶段以 demo/单机为主）
- 不测 auth/权限（out of scope）
# How to run
- pytest -q
- 指定子目录：
  - pytest -q tests/kb
  - pytest -q tests/stream
- 常见失败排查：env 是否污染、服务是否重启
# Fault Injection（破坏性实验）
- tests/runs/test_runs_compare_get.py：“向 runs.jsonl 注入坏行 → /runs/compare/{id} 仍返回 200，且 bad_lines > 0，同时 records 仍可用。”
- tests/runs/test_runs_compare_get.py：“compare 只剩 A（B 缺失）→ /runs/compare/{id} 仍 200，返回 records_count=1 + warning，并尽量返回已有记录。”
- tests/chat/test_chat_error_contract.py（锁 /chat 502 + detail 字段完整）
- tests/stream/test_stream_error_contract.py（锁 event:error JSON 字段完整）
- tests/stream/test_stream_error.py（锁 meta→error 的顺序）
- tests/chat/test_chat_rag_contract.py（锁：use_kb=true 时 metadata.rag 存在；空库时 citations=[] 且仍 200）
- tests/stream/test_stream_rag_contract.py（锁：meta.rag 摘要存在；usage.rag.citations 为 list；空库仍 meta→usage→done）
---
# Keywords
contract test, invariant, pytest, monkeypatch, tmp_path, isolation, bad_lines, warning, SSE order, 502 detail, event:error, degrade
# QA Seeds
{"qid":"q001","question":"为什么用契约测试而不是测模型回答语义？","expected_keywords":["契约测试","模型语义","mock","接口行为","证据链","稳定性","不可预测","测试定位"],"min_hits":2,"expected_sources":["Testing Strategy"],"note":"考察测试选型的核心逻辑，区分契约测试与语义测试的适用边界"}
{"qid":"q002","question":"为什么stream错误是200+event:error？如何被测试锁死？","expected_keywords":["stream","SSE","HTTP200","event:error","状态码","契约","测试用例","锁死","流式通道"],"min_hits":2,"expected_sources":["Testing Strategy"],"note":"考察SSE流式错误的契约设计原理，以及测试如何固化该行为不被破坏"}
{"qid":"q003","question":"bad_lines容错的价值是什么？为什么不直接失败？","expected_keywords":["bad_lines","容错","降级","服务可用","脏数据","不中断","鲁棒性","工程价值"],"min_hits":2,"expected_sources":["Testing Strategy"],"note":"考察脏数据容错的设计意义，以及服务稳定性优先的工程策略"}