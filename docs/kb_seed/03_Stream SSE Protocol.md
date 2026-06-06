# Header
- Title：03_Stream SSE Protocol
- Source：kb_seed
- Scope：只覆盖`/chat/stream`的SSE协议与解析；不讨论Prompt/RAG原理（它们再别篇）
- Files：`src/app/core/sse.py`、`src/app/api/routes_chat.py`（stream 分支）、`src/app/api/routes_demo.py`（解析端）
- Related Tests：
  - `tests/stream/test_stream_sse.py`
  - `tests/stream/test_stream_success_contract.py`
  - `tests/core/test_sse_format.py`
  - `tests/stream/test_stream_usage.py`
  - `tests/stream/test_stream_error_contract.py`
  - `tests/stream/test_stream_rag_contract.py`
# TL;DR
- `/chat/stream` 使用 SSE：`event:` + `data:` + 空行分隔事件块。
- 事件序列：`meta` → `token*` → `usage` → `done`（异常：`meta` → `error`）。
- 协议稳定性由契约测试锁死（格式、顺序、字段、错误语义）。
# Wire Format
- SSE block = 多行文本，以空行结束
- 每个 block 必须包含：
    - `event: <type>`
    - 至少 1 行 `data: ...`
- `data` 允许多行（多条 `data:` 会拼接成多行 payload）
- 推荐约定：
    - JSON payload 的 event：`meta/usage/error`
    - 纯文本 payload 的 event：`token/done`
- 分隔符：事件块之间必须有空行（逻辑上等价 `\n\n`，但要兼容 `\r\n\r\n`）
# Event Types & Payload Contract
## meta
- 目的：告诉前端“这次会话的上下文信息”
- data(JSON) 必含：
    - `trace_id`, `provider`, `model`
    - `prompt_id`, `prompt_version`
    - `rag`（只摘要：`enabled/top_k/hits/context_chars`）
## token
- 目的：增量输出
- data(plain text)：一个 token 或一个 chunk（你实现是 token 级别）
## usage
- 目的：最终统计与引用
- data(JSON) 必含：
    - `trace_id`, `provider`, `model`, `latency_ms`, `token_events`
    - `rag`（包含 citations/error）
## done
- data(plain text)：必须是 `[DONE]`
## error
- 语义：通道建立成功（HTTP 200）但下游失败
- data(JSON) 必含：
    - `trace_id`, `provider`, `model`, `latency_ms`, `error`
    - `rag` 摘要（enabled/top_k/hits/context_chars + error）
# Why HTTP 200 on error
- SSE 是“长连接通道”，200 表示通道建立成功
- 业务错误在通道内用 `event:error` 表达， 前端可持续按协议读取并做容错  
- 连接已建立，业务错误通过 `event:error` 传递（通道层与业务层分离）。  
- 对比 `/chat` 同步接口：失败用 502（请求/响应一次性完成）
# Reference Implementation Notes
- `sse_event()`：
    - dict/list 一律 JSON dumps（包括 `{}`/`[]`）
    - block 末尾空行终止（避免多余空块）
    - data 多行的处理策略
- stream handler：
    - meta 必须第一条（先构造完整再 yield）
    - usage 必须在 done 前出现（成功路径）
    - error 路径至少 meta→error（是否 done 以实现为准，写清楚）
- demo 解析器：
    - 兼容 `\r\n`
    - 只处理“完整块”（避免半包 JSON）
    - 跳过空块（避免 `types[0] is None`）
# Pitfalls & Debug Playbook
- curl 出现 `Could not resolve host: n`（原因：复制出字面量 `\n`；解决：bash 续行 `\`）
- meta JSONDecodeError（原因：data 为空或空块；解决：sse_event 序列化 + parser skip empty）
- 第一个事件 types[0]=None（原因：多余空块；解决：block 终止符 + parser）
- KB 空降级：仍要发 meta/usage/done（原因：契约锁死；解决：hits=0 citations=[]）
- `data:` vs `data: ` 兼容（解析端 trim）
- CRLF 兼容（split 前 normalize `\r\n`）
# Tests Mapping
- `tests/core/test_sse_format.py`：block 必须包含 event+data，且空行分隔
- `tests/stream/test_stream_success_contract.py`：meta→token*→usage→done
- `tests/stream/test_stream_error_contract.py`：error event JSON 字段完整
- `tests/stream/test_stream_rag_contract.py`：meta/usage 里 rag 字段存在（含降级）
---
# Keywords
`event, data, CRLF, \\n\\n, meta, token, usage, done, error, token_events, text/event-stream, event:error, latency_ms`

# QA Seeds
{"qid":"q001","question":"为什么 /chat/stream 下游失败时仍返回 HTTP 200，而不是 502？","expected_keywords":["SSE","通道","连接","event:error","业务错误","HTTP 200"],"min_hits":2,"expected_sources":["Stream SSE Protocol"],"note":"考察 SSE 通道层与业务层错误分离"}
{"qid":"q002","question":"SSE 的 data 多行该如何拼成最终 payload？","expected_keywords":["多行","data:","拼接","换行","payload","空行分隔"],"min_hits":2,"expected_sources":["Stream SSE Protocol"],"note":"考察多行 data 的解析规则与事件块边界"}
{"qid":"q003","question":"如何避免空事件块导致 meta 解析失败（types[0]=None 或 JSONDecodeError）？","expected_keywords":["\\n\\n","\\r\\n","空块","skip","trim","event: meta"],"min_hits":2,"expected_sources":["Stream SSE Protocol"],"note":"考察分隔符、CRLF 兼容与解析端跳过空块的策略"}