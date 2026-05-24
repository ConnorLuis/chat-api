from pydantic import BaseModel, Field, ConfigDict
from typing import List, Literal, Optional,Any

"""基于 Pydantic v2 定义 AI 聊天接口的全量数据模型
    覆盖「请求体（ChatRequest）」「消息结构（ChatMessage）」「响应体（ChatResponse）」「错误响应（ErrorResponse）」四类核心数据结构   
"""
# 聊天消息的最小单元，适配大语言模型的标准消息格式
class ChatMessage(BaseModel):
    # 定义消息角色字段：只能是“system”、“user”、“assistant”中的一个，默认user
    role: Literal["system", "user", "assistant"] = "user"
    # 定义消息内容字段：必须是字符串类型，无默认值
    content: str


# ChatRequest 模型定义：AI聊天接口的请求体规范
class ChatRequest(BaseModel):
    # 会话 ID -> 表示这个字段可以是str类型，也可以是None
    session_id: Optional[str] = Field(default=None, description="client session id for simple memory")
    # 消息列表 -> 表示这个字段是一个列表，且列表中的每个元素都必须是ChatMessage类型
    messages: List[ChatMessage]
    # 温度系数，控制AI回复的随机性，默认0.7是常用平衡值
    temperature: float = 0.7
    # 核采样参数，又称累积概率，AI 会只从概率总和达到 top_p 的候选词中选
    top_p: float = 0.9
    # 最大token数，AI处理文本的基本单位，表示AI回复最多256个令牌的内容，防止回复过长。
    max_tokens: int = 256
    # 选择器，诉后端代码：“本次聊天请求，需要使用哪一个 AI 服务 / 模型引擎来处理并生成回复”。
    # 限制只能mock或ollama回复，避免传入无效值
    provider: Literal["mock", "ollama"] = "mock"

    prompt_id: str | None = None
    prompt_version: str | None = None
    prompt_vars: dict | None = None

    use_kb: bool = False
    kb_top_k: int | None = None

    # 模型配置：添加JSON Schema示例，用于自动生成接口文档
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "provider": "mock",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 64,
                },
                {
                    "provider": "ollama",
                    "messages": [{"role": "user", "content": "一句话解释RAG"}],
                    "max_tokens": 128,
                    "temperature": 0.7,
                    "top_p": 0.9,
                },
                {
                    "provider": "mock",
                    "prompt_id": "chat",
                    "prompt_version": "v1",
                    "prompt_vars": {},
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 64
                }
            ]
        })

class Citation(BaseModel):
    doc_id: str
    chunk_id: str
    source: str
    title: str | None = None

class RagMetadata(BaseModel):
    enabled: bool
    top_k: int
    citations: List[Citation]
    hits: Optional[int] = None

# 封装响应的元信息（引擎类型、模型名、响应耗时），作为 ChatResponse 的可选字段
class ChatMetadata(BaseModel):
    provider: str
    # 这里已经使用字符串”unknown“兜底
    model: str
    latency_ms: int
    prompt_id: str | None = None
    prompt_version: str | None = None
    rag: Optional[RagMetadata] = None
    context_chars: int | None = None
    rag_error: str | None = None

# ChatResponse响应模型
class ChatResponse(BaseModel):
    # 追踪 ID -> 分布式系统中用于全链路追踪的唯一标识，即给每一次接口请求分配一个独一无二的ID
    # 作用：排查问题时，能通过这个 ID 快速定位某次请求的日志、执行流程；也能让客户端和服务端对齐 “某次请求的结果”，避免混淆。
    trace_id: str
    # 会话 ID -> 和 ChatRequest 中的 session_id 对应，返回客户端传入的会话 ID（如果有），用于维持用户的聊天上下文（比如多轮对话记忆）。
    session_id: Optional[str] = None
    # AI 针对用户请求生成的最终回复内容，也是响应中最核心的字段。
    answer: str
    # 定义元数据
    metadata: ChatMetadata | None = None
    # 模型配置：添加响应示例
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "trace_id": "95b3e35d-4593-444b-b8ce-040e944794e9",
                    "session_id": None,
                    "answer": "[mock] you said: hi",
                    "metadata": {
                        "provider": "mock",
                        "model": "unknown",
                        "latency_ms": 0,
                    }
                },
                {
                    "trace_id": "95b3e35d-4593-444b-b8ce-040e944794e9",
                    "session_id": None,
                    "answer": "[ollama] you said: hi",
                    "metadata": {
                        "provider": "ollama",
                        "model": "qwen2.5:7b",
                        "latency_ms": 12,
                    }
                }
            ]
        }
    )

"""接口异常时的标准化错误响应模型 ErrorDetail + ErrorResponse"""
class ErrorDetail(BaseModel):
    # trace_id（溯源）、provider（出错引擎）、model（出错模型）、latency_ms（出错耗时）、error（错误描述）
    trace_id: str
    provider: str
    model: str
    latency_ms: int
    error: str

# 外层包装，符合 FastAPI 错误响应的默认格式（detail 字段）
class ErrorResponse(BaseModel):
    detail: ErrorDetail

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "detail": {
                        "trace_id": "f519bbe1-550c-41f3-a3ac-957a1e6dd94e",
                        "provider": "ollama",
                        "model": "qwen2.5:7b",
                        "latency_ms": 15,
                        "error": "ollama failed: [Errno 111] Connection refused",
                    }
                }
            ]
        }
    )


# 提示词相关参数，做提示词ab测试共同的参数
class PromptRef(BaseModel):
    prompt_id: str
    prompt_version: str="v1"
    prompt_vars: dict[str, Any] = Field(default_factory=dict)


# 提示词对比请求
class PromptCompareRequest(BaseModel):
    provider: Literal["mock", "ollama"] = "mock"
    messages: List[ChatMessage]
    prompt_a: PromptRef
    prompt_b: PromptRef
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 256

# 提示词对比项
class PromptCompareItem(BaseModel):
    trace_id: str
    answer: str
    metadata: ChatMetadata

# 提示词对比指标
class PromptCompareMetrics(BaseModel):
    latency_ms_a: int
    latency_ms_b: int
    diff_latency_ms: int
    output_chars_a: int
    output_chars_b: int
    output_chars_diff: int

# 提示词对比响应体
class PromptCompareResponse(BaseModel):
    compare_group_id: str
    a: PromptCompareItem
    b: PromptCompareItem
    metrics: PromptCompareMetrics

# 提示词列表响应体
class PromptsListResponse(BaseModel):
    prompts: dict[str, list[str]]

# 运行记录
class RunRecord(BaseModel):
    trace_id: str
    mode: str
    provider: str
    model: str
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    latency_ms: int
    token_events: Optional[int] = None
    output_chars: Optional[int] = None
    prompt_chars: Optional[int] = None
    error: Optional[str] = None
    compare_group_id: Optional[str] = None
    variant: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None

# 运行踪迹响应体
class RunsTraceResponse(BaseModel):
    trace_id: str
    records: List[RunRecord]
    bad_lines: int
