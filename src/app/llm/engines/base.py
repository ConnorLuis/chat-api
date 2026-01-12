from abc import ABC, abstractmethod
from typing import  AsyncIterator, List
from src.app.llm.schemas import ChatMessage

"""通用的 LLM（大语言模型）引擎抽象基类 LLMEngine
    通过抽象方法规定所有具体引擎（如 MockEngine、OllamaEngine）
    必须实现的核心接口（非流式 generate、流式 stream），
    保证不同引擎的接口一致性，实现 “多态” 和 “开闭原则”
    
    抽象基类（ABC）：不能被实例化，仅用于定义接口规范，子类必须实现所有 @abstractmethod 装饰的方法，否则无法实例化；
    抽象方法：只有方法签名（参数、返回值），没有具体实现（仅抛 NotImplementedError），强制子类重写；
    作用：统一子类的接口，避免不同引擎实现时出现方法名 / 参数不一致的问题
"""
class LLMEngine(ABC):
    name: str = "base"

    # 非流式生成回复, 同步非流式生成回复的核心接口
    @abstractmethod
    def generate(self, messages: List[ChatMessage], temperature: float, top_p: float, max_tokens: int) -> str:
        raise NotImplementedError

    # 异步流式生成回复, 异步流式生成回复的核心接口
    @abstractmethod
    async def stream(self, messages: List[ChatMessage], temperature: float, top_p: float, max_tokens: int) -> AsyncIterator[str]:
        raise NotImplementedError