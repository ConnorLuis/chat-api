import asyncio
from typing import AsyncIterator, List
from src.app.llm.schemas import ChatMessage
from .base import LLMEngine

"""测试用的 Mock 引擎类 MockEngine
    实现非流式的 generate 方法：模拟 AI 生成回复（本质是返回用户最后一条输入的 “回声”）；
    实现异步流式的 stream 方法：模拟 AI 逐字返回回复的效果（流式输出）；
    全程不调用真实 AI 模型，仅用于接口测试、前端联调等场景，和你之前 curl 得到的 [mock] you said: hi day2 响应完全对应。
"""

class MockEngine(LLMEngine):
    name = "mock"

    # generate（非流式生成回复）
    def generate(self, messages: List[ChatMessage], temperature: float, top_p: float, max_tokens: int) -> str:
        last_user = ""
        # 反向遍历消息列表，找到最后一条用户信息
        for m in reversed(messages):
            if m.role == "user":
                last_user = m.content
                break
        # 返回mock回复，截取前200个字符防止内容过长
        return f"[mock] you said: {last_user[:200]}"

    # stream（流式生成回复）
    async def stream(self, messages: List[ChatMessage], temperature: float, top_p: float, max_tokens: int) -> str:
        # 调用 generate 拿到完整的 mock 回复
        text = self.generate(messages, temperature, top_p, max_tokens)
        # 逐字符遍历，模拟流式输出
        for ch in f"[mock-stream] {text}":
            yield ch # 逐个返回字符
            await asyncio.sleep(0.01) # 延迟0.01秒，模拟真实流式回复的间隔