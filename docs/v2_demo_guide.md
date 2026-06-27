# chat-api v2 Demo Guide

## 1. Demo 目标

本文档用于演示 `chat-api` v2 的完整能力链路。它不是系统设计说明，而是一份可以按顺序执行的演示脚本。

演示目标：

## 2. 环境准备
### 2.1 激活环境
cd ~/projects/chat-api
conda activate chatapi
### 2.2 设置 Ollama 地址

如果 Ollama 安装在 Windows，而服务运行在 WSL2 中，需要设置 Windows 网关 IP：

WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"

确认 Windows 侧已经有模型：

ollama pull qwen2.5:7b
### 2.3 启动服务
python -m uvicorn src.app.main:app --reload --port 8000

另开一个终端执行后续命令。

## 3. Health Check
curl -s http://localhost:8000/health | cat

预期：

{"status":"ok"}

讲解点：

/health 是最小可用服务探针，用于确认 FastAPI 服务已经启动。
## 4. Sync Chat：同步聊天
### 4.1 Mock provider
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"mock",
    "messages":[{"role":"user","content":"hi"}]
  }' | python -m json.tool

观察字段：

trace_id
answer
metadata.provider
metadata.model
metadata.latency_ms

讲解点：

mock provider 用于稳定测试，不依赖本地模型服务。
### 4.2 Ollama provider
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"一句话解释 RAG"}],
    "max_tokens":128
  }' | python -m json.tool

讲解点：

ollama provider 代表真实本地 LLM 调用链路。
metadata 中会返回 provider、model、latency_ms。
## 5. Stream Chat：SSE 流式聊天
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"用两句话解释 SSE 流式输出"}],
    "max_tokens":128
  }'

预期事件顺序：

event: meta
event: token
event: token
...
event: usage
event: done

讲解点：

/chat/stream 使用 SSE 协议。
同步接口失败时用 HTTP 502；
流式接口失败时通常通过 event:error 表达业务错误。
## 6. Reset + Seed KB

为了保证 RAG 演示稳定，先清理 runtime KB，再重新入库固定的 docs/kb_seed/01-11。

### 6.1 停止 uvicorn

在服务终端按：

Ctrl+C
### 6.2 Reset runtime artifacts
python scripts/run_rag_eval_workflow.py --reset-runtime --yes

预期输出：

reset runtime artifacts:
  removed: kb/chroma
  removed: kb/docs
  removed: kb/docs.jsonl
Runtime artifacts were reset. Restart uvicorn, then rerun this workflow without --reset-runtime to seed/evaluate.
### 6.3 重启 uvicorn
WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"

python -m uvicorn src.app.main:app --reload --port 8000
### 6.4 Seed KB

另一个终端执行：

python scripts/seed_kb.py --ingest

预期：

selected documents: 11
manifest written: eval/kb_seed_manifest.jsonl

讲解点：

Day29 新增 seed_kb.py，固定 seed 文档范围、source、title 和 manifest。
这样避免手工入库导致 title/source metadata 不一致。
## 7. RAG Sync Chat：同步 RAG 问答
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"mock",
    "messages":[{"role":"user","content":"项目中 docs.jsonl 的作用是什么？"}],
    "use_kb": true,
    "kb_top_k": 3
  }' | python -m json.tool

重点观察：

metadata.rag.enabled
metadata.rag.hits
metadata.rag.context_chars
metadata.rag.citations
metadata.rag.citations[].source
metadata.rag.citations[].title

预期 citation 中能看到类似：

source = docs/kb_seed/07_KB Ingest & Search.md
title = KB Ingest & Search

讲解点：

RAG 会先检索 KB，再把命中的 chunks 注入为 system context。
citations 用于回答溯源。
## 8. Hybrid RAG Metadata

继续使用 RAG 请求，观察 Day28 暴露的 Hybrid RAG 字段：

curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"mock",
    "messages":[{"role":"user","content":"candidate_k 在 RAG 中用来做什么？"}],
    "use_kb": true,
    "kb_top_k": 3
  }' | python -m json.tool

重点字段：

metadata.rag.backend
metadata.rag.retrieval_mode
metadata.rag.fusion
metadata.rag.vector_weight
metadata.rag.lexical_weight
metadata.rag.embedding_ms
metadata.rag.retrieval_ms
metadata.rag.rerank_ms
metadata.rag.context_build_ms
metadata.rag.total_ms

预期：

retrieval_mode = hybrid
fusion = vector_lexical
vector_weight = 0.7
lexical_weight = 0.3

讲解点：

Day28 将 RAG rerank 从向量分数扩展为 Hybrid RAG：
vector retrieval + lexical scoring + fusion rerank。
外部请求字段不变，新增字段只作为 observability metadata 暴露。
## 9. RAG Streaming：流式 RAG
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"RAG 的最小闭环包括哪些步骤？"}],
    "prompt_id":"qa_strict",
    "prompt_version":"v1",
    "use_kb": true,
    "kb_top_k": 3,
    "max_tokens": 128
  }'

重点观察：

event: meta
data.rag.enabled
data.rag.backend
data.rag.retrieval_mode

event: usage
data.rag.citations
data.rag.total_ms

讲解点：

同步和流式接口共享同一套 RAGBackend 构建逻辑。
stream 的 meta.rag 与 usage.rag 都会暴露 RAG metadata。
## 10. Prompt Compare
curl -s -X POST http://localhost:8000/prompt/compare \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"解释 RAG 为什么能提升回答可靠性"}],
    "max_tokens":128,
    "temperature":0.7,
    "top_p":0.9,
    "prompt_a":{"prompt_id":"chat","prompt_version":"v1","prompt_vars":{}},
    "prompt_b":{"prompt_id":"qa_strict","prompt_version":"v1","prompt_vars":{}}
  }' | python -m json.tool

重点观察：

compare_group_id
a.trace_id
b.trace_id
a.metadata.prompt_id
b.metadata.prompt_id
metrics

讲解点：

Prompt Compare 用同一个输入对比两套 prompt。
两条运行记录会写入 run log，并共享 compare_group_id。
## 11. Run Replay
### 11.1 按 trace_id 回放

将上一步中的某个 trace_id 替换到命令中：

curl -s http://localhost:8000/runs/trace/<trace_id> | python -m json.tool
### 11.2 按 compare_group_id 回放

将上一步中的 compare_group_id 替换到命令中：

curl -s http://localhost:8000/runs/compare/<compare_group_id> | python -m json.tool

讲解点：

Run Replay 让 prompt 实验可回放、可审计、可复盘。
## 12. RAG Eval Workflow

Day29 将手工 QA20 评测收敛为一条 workflow。

### 12.1 Reset runtime

先停止 uvicorn，然后执行：

python scripts/run_rag_eval_workflow.py --reset-runtime --yes

然后重启 uvicorn。

### 12.2 Run workflow
python scripts/run_rag_eval_workflow.py \
  --provider ollama \
  --results eval/results/rag_eval_20_day29_workflow.jsonl \
  --summary eval/results/rag_eval_20_day29_workflow_summary.json \
  --report eval/reports/rag_eval_report_day29_workflow.md

workflow 会执行：

health check
→ seed KB
→ provider warmup
→ QA20 eval
→ strict report
→ print summary

预期：

All regression gates passed!

最新验证结果：

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

讲解点：

seed_kb.py 解决 KB 状态不可复现问题；
run_rag_eval_workflow.py 解决评测命令分散问题；
provider warmup 解决 Ollama 首次请求污染 p95 latency 的问题。
## 13. Error Demo
### 13.1 同步错误

停止 uvicorn，设置错误的 Ollama 地址后重启：

export OLLAMA_BASE_URL=http://127.0.0.1:1
python -m uvicorn src.app.main:app --reload --port 8000

请求：

curl -i -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"hi"}]
  }'

预期：

HTTP 502
detail.trace_id
detail.provider
detail.model
detail.latency_ms
detail.error
### 13.2 流式错误
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"ollama",
    "messages":[{"role":"user","content":"hi"}],
    "max_tokens":8
  }'

预期：

event: meta
event: error

讲解点：

同步接口用 HTTP 502 表达下游失败；
流式接口通常已经建立 HTTP 200 连接，因此通过 event:error 表达业务失败。

演示结束后恢复 Ollama 地址并重启服务：

WIN_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_BASE_URL="http://$WIN_IP:11434"

python -m uvicorn src.app.main:app --reload --port 8000
## 14. 测试与 CI

本地测试：

pytest -q

当前预期：

63 passed

CI：

GitHub Actions
push to all branches
pytest -q
EMBEDDING_PROVIDER=mock

讲解点：

CI 使用 mock embedding 和 mock provider 保护基础 contract；
本地 workflow 使用 ollama 验证真实 RAG QA20。
## 15. 运行时产物清理

演示和评测可能产生以下运行时产物：

kb/chroma/
kb/docs/
kb/docs.jsonl
eval/kb_seed_manifest.jsonl
eval/results/
eval/reports/
runs/prompt_runs.jsonl

一般不要提交：

git restore kb/chroma kb/docs.jsonl kb/docs 2>/dev/null || true

rm -f eval/kb_seed_manifest.jsonl
rm -f eval/results/rag_eval_20_day29_workflow.jsonl
rm -f eval/results/rag_eval_20_day29_workflow_summary.json
rm -f eval/reports/rag_eval_report_day29_workflow.md

git restore eval/reports 2>/dev/null || true

最终提交前检查：

git status