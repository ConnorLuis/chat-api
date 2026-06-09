from abc import ABC, abstractmethod

from src.app.rag.schemas import RAGContextResult


class RAGBackend(ABC):
    """RAG 后端抽象基类"""

    @abstractmethod
    def build_context(self, query: str, top_k: int) -> RAGContextResult:
        """
        构建 RAG 上下文
        
        Args:
            query: 用户查询文本
            top_k: 返回的文档数量
            
        Returns:
            RAGContextResult: RAG 上下文结果
        """
        raise NotImplementedError
