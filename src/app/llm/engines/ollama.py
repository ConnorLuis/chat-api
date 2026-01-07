import os
import httpx
from typing import AsyncIterator, List
from src.app.llm.schemas import ChatMessage
from .base import LLMEngine

"""对接本地 Ollama 服务的真实 AI 引擎类 OllamaEngine
    封装 Ollama 的 HTTP API 调用逻辑，对外提供统一的 generate（非流式）和 stream（异步流式）方法；
    支持配置 Ollama 服务地址、模型名称、超时时间，具备环境变量适配能力；
    将业务侧的 ChatMessage 消息列表转换为 Ollama 能识别的 prompt 格式，完成参数映射和请求发送。
"""

class OllamaEngine(LLMEngine):
    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str = "qwen2.5:7b", timeout_s: float = 60.0):
        # 分为三块优先级：传入的base_url > 环境变量OLLAMA_BASE_URL > 默认值(本地11434端口)
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.model = model # 默认使用通义千问2.5 7B模型
        self.timeout_s = timeout_s # 请求超时时间60秒

    # 辅助方法：消息转换成prompt形式，方便识别
    def _to_prompt(self, messages: List[ChatMessage]) -> str:
        lines = []
        for m in messages:
            lines.append(f"{m.role}: {m.content}")
        return "\n".join(lines)

    # 核心方法：generate（非流式生成回复）
    def generate(self, messages: List[ChatMessage], temperature: float, top_p: float, max_tokens: int) -> str:
        # 转换消息为prompt
        prompt = self._to_prompt(messages)
        # 组装Ollama API的请求参数
        payload = {
            "model": self.model, # 初始化模型名
            "prompt": prompt, # 转换后的prompt
            "stream": False, # 非流式，一次性返回结果
            "options": { # 生成参数映射
                "temperature": temperature, # 随机性
                "top_p": top_p, # 核采样
                "num_predict": max_tokens, # 最大token数
            },
        }
        # 同步调用Ollama API
        with httpx.Client(timeout=self.timeout_s) as client:
            # 发出请求
            r = client.post(f"{self.base_url}/api/generate", json=payload)
            # 抛出HTTP错误，方便上层捕获
            r.raise_for_status()
            data = r.json() # 解析json响应
            return data.get("response", "") # 返回AI生成的回复内容

    # 核心方法：stream（流式生成回复）
    async def stream(self, messages: List[ChatMessage], temperature: float, top_p: float, max_tokens: int) -> str:
        # 转换消息为prompt
        prompt = self._to_prompt(messages)
        # 组装Ollama API的请求参数
        payload = {
            "model": self.model, # 初始化模型名
            "prompt": prompt, # 转换后的prompt
            "stream": True, # 非流式，一次性返回结果
            "options": { # 生成参数映射
                "temperature": temperature, # 随机性
                "top_p": top_p, # 核采样
                "num_predict": max_tokens, # 最大token数
            },
        }
        # 异步调用Ollama流式API
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            # stream="POST" 表示异步流式接收响应
            async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as r:
                r.raise_for_status()
                # 逐行读取流式响应（Ollama每行返回一个JSON对象）
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = httpx.Response(200, content=line).json()
                    except Exception:
                        continue
                    token = obj.get("response", "")
                    if token:
                        yield token # 逐个返回分片token，模拟打字机效果
                    if obj.get("done"): # Ollama返回done=true表示流式结束
                        break