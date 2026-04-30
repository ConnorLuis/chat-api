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

    @property
    def PROMPTS_DIR(self) -> str:
        return getenv("PROMPTS_DIR", "prompts")

    @property
    def RUN_LOG_PATH(self) -> str:
        return getenv("RUN_LOG_PATH", "runs/prompt_runs.jsonl")


settings = Settings()