import os

# 健壮的环境变量读取
# 解决了原生 os.getenv 的 “空字符串” 边界问题
def getenv(key: str, default: str) -> str:
    v = os.getenv(key)
    return default if v is None or v == "" else v

"""封装所有配置项

"""
class Settings:
    # Ollama 服务的基础地址	http://127.0.0.1:11434	直接返回字符串
    @property
    def OLLAMA_BASE_URL(self) -> str:
        return getenv("OLLAMA_BASE_URL", "http://127.0.0.1:9999")

    # 默认使用的 Ollama 模型名	qwen2.5:7b	直接返回字符串
    @property
    def OLLAMA_MODEL(self) -> str:
        return getenv("OLLAMA_MODEL", "qwen2.5:7b")

    # Ollama API 调用的超时时间（秒）	60	先读取字符串，再转 float 类型
    @property
    def OLLAMA_TIMEOUT_S(self) -> float:
        return float(getenv("OLLAMA_TIMEOUT_S", "60"))

    # OpenAI / OpenAI-compatible Provider 配置
    @property
    def OPENAI_API_KEY(self) -> str:
        return getenv("OPENAI_API_KEY", "")

    @property
    def OPENAI_BASE_URL(self) -> str:
        return getenv("OPENAI_BASE_URL", "")

    @property
    def OPENAI_MODEL(self) -> str:
        return getenv("OPENAI_MODEL", "")

    @property
    def OPENAI_TIMEOUT_S(self) -> float:
        return float(getenv("OPENAI_TIMEOUT_S", "60"))

    # 提示词模板的地址
    @property
    def PROMPTS_DIR(self) -> str:
        return getenv("PROMPTS_DIR", "prompts")

    # 运行后日志保存地址
    @property
    def RUN_LOG_PATH(self) -> str:
        return getenv("RUN_LOG_PATH", "runs/prompt_runs.jsonl")

    # knowledge book 地址
    @property
    def KB_DIR(self) -> str:
        return getenv("KB_DIR", "kb")

    # kb的向量数据库chroma地址，Chroma persist 目录
    @property
    def KB_CHROMA_DIR(self) -> str:
        return getenv("KB_CHROMA_DIR", os.path.join(self.KB_DIR, "chroma"))

    # 向量数据库chroma的collection名
    @property
    def KB_COLLECTION(self) -> str:
        return getenv("KB_COLLECTION", "kb_chunks")

    # 切块大小
    @property
    def KB_CHUNK_SIZE(self) -> int:
        return int(getenv("KB_CHUNK_SIZE", "800"))

    # 重叠大小
    @property
    def KB_CHUNK_OVERLAP(self) -> int:
        return int(getenv("KB_CHUNK_OVERLAP", "120"))

    # 检索返回多少条
    @property
    def KB_TOP_K(self) -> int:
        return int(getenv("KB_TOP_K", "3"))

    @property
    def KB_CANDIDATE_K(self) -> int:
        return int(getenv("KB_CANDIDATE_K", "50"))

    @property
    def KB_MAX_CONTEXT_CHARS(self) -> int:
        return int(getenv("KB_MAX_CONTEXT_CHARS", "2000"))

    # 决定用 mock 还是 SentenceTransformer
    @property
    def EMBEDDING_PROVIDER(self) -> str:
        return getenv("EMBEDDING_PROVIDER", "mock")

    # hf 模型路径/名字
    @property
    def EMBEDDING_MODEL(self) -> str:
        return getenv("EMBEDDING_MODEL", "/mnt/f/LLM/maidalun/bce-embedding-base_v1")

    # 文档地址
    @property
    def DOCS_DIR(self) -> str:
        return getenv("DOCS_DIR", os.path.join(self.KB_DIR, "docs"))

    #索引文件类型
    @property
    def INDEX_FILE(self) -> str:
        return getenv("INDEX_FILE", os.path.join(self.KB_DIR, "docs.jsonl"))

    # 文本向量化后维度
    @property
    def EMBEDDING_DIM(self) -> str:
        return getenv("EMBEDDING_DIM", "512")

    # RAG 后端类型（native/其他）
    @property
    def RAG_BACKEND(self) -> str:
        return getenv("RAG_BACKEND", "native").lower()


settings = Settings()