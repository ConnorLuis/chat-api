from pydantic import BaseModel, Field
from typing import List, Literal, Optional

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

# ChatResponse响应模型
class ChatResponse(BaseModel):
    # 追踪 ID -> 分布式系统中用于全链路追踪的唯一标识，即给每一次接口请求分配一个独一无二的ID
    # 作用：排查问题时，能通过这个 ID 快速定位某次请求的日志、执行流程；也能让客户端和服务端对齐 “某次请求的结果”，避免混淆。
    trace_id: str
    # 会话 ID -> 和 ChatRequest 中的 session_id 对应，返回客户端传入的会话 ID（如果有），用于维持用户的聊天上下文（比如多轮对话记忆）。
    session_id: Optional[str] = None
    # AI 针对用户请求生成的最终回复内容，也是响应中最核心的字段。
    answer: str