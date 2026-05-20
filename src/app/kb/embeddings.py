import hashlib
import math
from src.app.core.settings import Settings
from abc import ABC, abstractmethod
from sentence_transformers import SentenceTransformer

"""
统一接口：EmbeddingEngine
    dim： 向量维度
    embed_query(text): 批量embed（入库用）
    embed_query(query): 单挑embed（检索用）
上层 routes_kb 不关心用的是什么模型，只要能得到向量即可。
"""
class EmbeddingEngine(ABC):
    @property
    @abstractmethod
    def dim(self) -> int:
        pass

    @abstractmethod
    def embed_documents(self, embeddings: list[str]) -> list[list[float]]:
        pass

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        pass

# 把文本 hash 成一个固定向量（可复现）
class MockEmbeddingEngine(EmbeddingEngine):
    def __init__(self, dim: int):
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, embeddings: list[str]) -> list[list[float]]:
        results = []
        for text in embeddings:
            # sha256(text) 得到 64 hex 字符串
            hash_object = hashlib.sha256(text.encode("utf-8"))
            # 逐维取 hex 字符转成 0~15 的数，再除以 15 得到 0~1 之间的浮点
            hash_hex = hash_object.hexdigest()

            vector = []
            for i in range(self.dim):
                char_val = int(hash_hex[i % len(hash_hex)], 16)
                vector.append(char_val / 15.0)
            # 做 L2 normalize（单位向量）保证余弦相似度可用
            norm = math.sqrt(sum(x**2 for x in vector))
            if norm > 0:
                vector = [x / norm for x in vector]
            results.append(vector)
        return results


    def embed_query(self, query: str) -> list[float]:
        return self.embed_documents([query])[0]

# 真实语义模型
class HFEmbeddingEngine(EmbeddingEngine):
    # init 时加载模型并读维度：get_sentence_embedding_dimension()
    # embed_documents：批量 encode（normalize_embeddings=True）
    # embed_query：单条 encode（normalize_embeddings=True）
    def __init__(self, model_name_or_path: str, device: str=None, **kwargs):
        self.model = SentenceTransformer(model_name_or_path=model_name_or_path, device=device, **kwargs)
        self._dim = self.model.get_sentence_embedding_dimension()

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str], batch_size: int=32) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            batch_size = batch_size,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self.dim

        embedding = self.model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        return embedding.tolist()

def get_embedding_engine(settings: Settings) -> EmbeddingEngine:
    provider = settings.EMBEDDING_PROVIDER

    if provider == "mock":
        return MockEmbeddingEngine(dim=int(settings.EMBEDDING_DIM))
    elif provider == "hf":
        return HFEmbeddingEngine(model_name_or_path=settings.EMBEDDING_MODEL)
    else:
        raise ValueError("只支持 mock / hf 两种嵌入引擎")