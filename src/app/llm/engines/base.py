from abc import ABC, abstractmethod
from typing import  AsyncIterator, List
from src.app.llm.schemas import ChatMessage


class LLMEngine(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, messages: List[ChatMessage], temperature: float, top_p: float, max_tokens: int) -> str:
        raise NotImplementedError

    @abstractmethod
    async def stream(self, messages: List[ChatMessage], temperature: float, top_p: float, max_tokens: int) -> str:
        raise NotImplementedError