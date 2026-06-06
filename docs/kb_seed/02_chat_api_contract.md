# 标题与元信息
- title：Chat API Contract
- Source：kb_seed
- Scope：说明chat路由接口，请求响应以及对应的契约测试
- files：
	- `src/app/api/routes_chat.py`
	- `src/app/core/sse.py`
	- `src/app/llm/schemas.py`
- endpoints:
	- POST /chat  
	- POST /chat/stream  
# 契约导向
- `/chat`：成功 200，失败 502(detail=结构化错误)
- `/chat/stream`：SSE 事件序列 meta→token*→usage→done；失败用 event:error
- RAG：开启后 meta/usage/error 都包含 rag 摘要与 citations
## Data Models
- `ChatMessage`：`role ∈ {system,user,assistant}`（客户端显式传入；服务端可能做兜底但不建议依赖）
- `ChatRequest`：写必填字段 + 可选字段 + 默认值策略（只写行为，不写代码）
	- 必填：`provider`模型引擎, `messages` 消息列表
	- 可选：`prompt_id/prompt_version/prompt_vars`, `use_kb/kb_top_k`, `max_tokens/temperature/top_p`
- `ChatResponse`：`trace_id`, `answer`模型回答, `metadata`元数据
- `ChatMetadata`：
	- `provider/model/latency_ms`：模型引擎/模型/生成回复耗时
	- `prompt_id/prompt_version`：提示词模板id/提示词模板版本
	- `rag.enabled/top_k/hits/context_chars/citations/error`
- `ErrorResponse`：
	- `trace_id/provider/model/latency_ms/error`
## POST /chat/stream (SSE) 
### A. HTTP层契约
- response header：Content-Type: text/event-stream
- 状态码：成功建立通道status_code=200；业务错误保持status_code=200,通过event:error返回错误信息，保持event的SSE一致性
- 连接结束语义：done事件作为正常结束，错误路径会发送 `event:error`；不保证 usage/done 出现（以实现为准）。
### B.SSE block格式
- 每个事件块
- `event: <type>\n`
- `data: <payload>\n`(允许多行data)
- `\n`（空行结束一个事件块）
- 每个事件块都是进入sse_event方法构建sse块形式，其中`meta/usage/error`的data是JSON格式，`token/done`的data格式是纯字符串
### C. 事件类型与顺序
- 正常：`meta`->`token`(0..N)->`usage`->`done`
- 异常：**通道仍为 200**，且 **meta 一定先发**；随后可能发 `error` 并结束（不保证 usage/done 出现，按实现而定）。
- 强调：`meta`永远是第一条，`done`最后”限定为“正常路径”
### D. 每个事件的 payload 结构
`meta.data`必含：`trace_id/provider/model/prompt_id/prompt_version`
`meta.data.rag`至少含：`enabled/top_k/hits/context_chars`，`RAG：开启后 meta 含 rag 摘要；usage/error 含 citations 与 rag.error。`
`usage.data` 必含：`trace_id/provider/model/latency_ms/token_events/prompt_id/prompt_version`
`usage.data.rag`必含：`enabled/top_k/hits/context_chars/citations/error`
`error.data`必含：`trace_id/provider/model/latency_ms/error/prompt_id/prompt_version` 必须结构化JSON
`error.data.rag`必含：`enabled/top_k/hits/context_chars/citations/error`
### E. RAG 的 stream 语义
- `use_kb=true` 但无命中：`rag.hits=0`、`citations=[]`、`rag.error` 可为 null（降级不是错误）
- KB 异常：`rag.error` 写入（usage 里 / error 里），但仍保证 meta 发出，前端可展示状态

# POST /chat
- `POST /chat` 成功：200 + `ChatResponse`（trace_id/answer/metadata）
- `POST /chat` 失败：502 + `detail` 结构化 JSON（字段列出来）
- RAG 开启：metadata.rag 中 citations 的位置与含义（不展开 chunking/chroma）
# Failure Modes
- LLM 不可达：`/chat` → 502 + `detail`（结构化 JSON）；`/chat/stream` → 200 + `event:error`
- KB 空/无命中：降级（hits=0, citations=[])
- KB 异常：rag.error 有值（仍可降级或在 stream 里发 error，按实现）
- 客户端中止：demo abort（可选一条）
## Contract Invariants (Locked by Tests)
- `meta`必须是第一条事件,且至少包含 `trace_id/provider/model` `tests/stream/test_stream_success_contract.py`
- `usage` 必须出现且包含 `latency_ms/token_events` `tests/stream/test_stream_success_contract.py`
- `done` 的 data 必须是 `[DONE]` `tests/stream/test_stream_success_contract.py`
- SSE事件必须完整`tests/stream/test_stream_usage.py`
- Mock 引擎生成的流式响应中，不仅能返回 token 类型的增量内容事件，还会返回 done 类型的结束事件；`tests/stream/test_stream_sse.py`
- 发生异常时，响应的content-type依旧符合SSE标准 `tests/stream/test_stream_error.py`
- 异常场景下 /chat/stream 接口返回的 error 类型 SSE 事件中，data 字段的 JSON 数据严格符合预设契约 —— 包含所有必填溯源字段（trace_id/provider/model/latency_ms/error）`tests/stream/test_stream_error_contract.py`
- /chat/stream 接口meta事件包含`prompt_id/version`等提示词模板信息。`tests/stream/test_stream_meta_has_prompt.py`
- /chat/stream 接口meta事件至少含 `enabled/top_k/hits/context_chars`等必要信息`tests/stream/test_stream_rag_contract.py`
---
# Keywords
`text/event-stream`, `event:`, `data:`, `\\n\\n`、`meta`, `token`, `usage`, `done`, `error`、`trace_id`, `latency_ms`, `token_events`、`prompt_id`, `prompt_version`、`use_kb`, `kb_top_k`, `citations`, `context_chars`, `rag.error`

# QA Seeds
{"qid":"q001","question":"/chat 接口与 /chat/stream 接口发生业务异常时，HTTP 状态码和返回形式有何区别？","expected_keywords":["502","HTTP 200","event:error","detail","结构化错误","SSE异常"],"min_hits":2,"expected_sources":["Chat API Contract"],"note":"考察两个聊天接口的异常处理策略与状态码契约"}
{"qid":"q002","question":"SSE 单个事件块的标准格式是什么，不同事件的 data 数据类型有哪些区分？","expected_keywords":["text/event-stream","event:","data:","\\n\\n","JSON格式","纯字符串","SSE块格式"],"min_hits":2,"expected_sources":["Chat API Contract"],"note":"考察SSE事件块基础格式与data载荷类型约定"}
{"qid":"q003","question":"meta 事件与 usage 事件中，RAG 模块要求包含哪些必填子字段？","expected_keywords":["rag.enabled", "rag.top_k","kb_top_k","hits","context_chars","citations","rag.error","trace_id"],"min_hits":2,"expected_sources":["Chat API Contract"],"note":"考察meta/usage事件内RAG相关必填字段契约"}