from .base import LLMEngine
from .mock import MockEngine
from .ollama import OllamaEngine

"""AI 引擎模块的 “入口文件”
    对外暴露统一的引擎获取接口 get_engine()；
    把不同的 AI 引擎（Mock/Ollama）进行封装，提供 “工厂模式” 的调用方式；
    让外部代码无需关心具体引擎的实现细节，只需传入 provider 参数就能拿到对应的引擎实例。
"""

# 定义引擎工厂函数
def get_engine(provider: str) -> LLMEngine:
    # 处理输入参数，保证鲁班
    p = (provider or "mock").lower()
    # 根据选择器选择的模型不同，调用不同引擎
    if p == "ollama":
        return OllamaEngine()
    return MockEngine()
