# 标题与元信息
- Title：Project Overview
- Source：kb_seed
- Scope：概览 chat-api 的能力模块、入口位置与验收证据（测试/可观测字段）。
- files：
	- app entry：`src/app/main.py`
	- chat：`src/app/api/routes_chat.py` + `src/app/core/sse.py`
	- prompts/runs：`src/app/llm/*` + `src/app/api/prompt/*` + `src/app/api/runs/*`
	- kb/rag：`src/app/api/kb/*` + `src/app/kb/*`
	- core：`src/app/core/settings.py` / `logging.py` / `errors.py`
	- demo：src/app/api/routes_demo.py
- endpoints：
	- POST /chat
	- POST /chat/stream
	- GET /demo
	- POST /kb/documents
	- GET /kb/search
	- GET /kb/documents
	- DELETE /kb/documents/{doc_id}
	- POST /prompt/compare
	- GET /prompts
	- GET /runs/trace/{trace_id}
	- GET /runs/compare/{compare_group_id}
# TL;DR
- 这是一个工程化 LLM Chat 服务骨架：sync `/chat` + SSE `/chat/stream` + `/demo` 演示台。
- 支持 PromptHub（prompt_id/version）、RAG（KB ingest/search + citations）与 A/B compare。
- 可观测与可靠性：trace_id + structured error + runs 回放 + 契约测试锁死。
# Interfaces
- `provider`（mock/ollama）
- `messages`（list of `{role, content}`）
- `prompt_id/prompt_version`（可选）
- `use_kb/kb_top_k`（可选）
- sampling params：`max_tokens/temperature/top_p`（可选）
- 输出：`trace_id` + `metadata(provider/model/latency_ms + rag)`
# Flow
- request parse + trace_id
- prompt render（可选）
- rag retrieve top_k（可选）→ context injection（可选）
- choose engine(provider)
- sync：generate → response(metadata + citations)
- stream：meta → token* → usage → done/error
- run log 落盘（trace_id/latency/rag/compare）
- tests contract（pytest 锁死）
# Failure Modes
- LLM 不可达：`/chat` → 502 + `detail`（结构化 JSON）；`/chat/stream` → 200 + `event:error`
- KB 空/检索失败：降级返回（hits=0、citations=[]、rag.error 非空或为空）
- 客户端中止：demo abort（可选一条）
# Tests
- `tests/chat/*`：/chat contract + prompt + rag
- `tests/stream/*`：SSE 顺序 contract + stream rag + error
- `tests/kb/*`：ingest/search/documents(list/delete)
- `tests/prompt/*`：compare contract、prompts list
- `tests/runs/*`：runs replay(trace/compare)
- `tests/demo/*`：demo 页面关键字锁死
---
# Keywords
/chat, /chat/stream, /demo, trace_id, latency_ms, SSE, meta, token, usage, done, error, prompt_id, prompt_version, use_kb, kb_top_k, citations, docs.jsonl, tombstone, context_chars, rag_error

# QA Seeds
{"qid":"q001","question":"为什么 stream 失败仍 HTTP 200，而用 `event:error`？","expected_keywords":["sse","stream","event:error","HTTP 200","流式推送","统一事件格式","异常封装","前端解析"],"min_hits":1,"expected_sources":["Project Overview"],"note":"考察 SSE 流式接口的错误处理设计与协议规范"}
{"qid":"q002","question":"docs.jsonl 的作用是什么，为什么不只用 doc_id.md？","expected_keywords":["元数据","tombstone","追加写入","审计","软删除","并发安全","索引","原始md文件"],"min_hits":2,"expected_sources":["Project Overview"],"note":"考察 docs.jsonl 设计目的、与原生md文件的分工及架构优势"}
{"qid":"q003","question":"RAG 开启时，哪些字段能证明真的检索并注入了上下文？","expected_keywords":["retrieve","hits","doc_id","chunk_id","上下文注入","score","source","trace_id", "context_chars", "citations", "kb_top_k/use_kb"],"min_hits":2,"expected_sources":["Project Overview"],"note":"考察 RAG 链路里检索、上下文注入环节的可观测溯源字段"}