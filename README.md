# chat-api

一个极简的 FastAPI 聊天服务，包含：

- `/health` 健康检查

- `/chat` 同步聊天（mock / ollama）

- `/chat/stream` 流式聊天（mock / ollama）

- 全局中间件：`x-trace-id` + 延迟日志记录

## 要求

- WSL2 Ubuntu（推荐）+ conda 环境

- Python 3.10+

- （可选）运行在 Windows 上的 Ollama

## 快速入门

### 1) 创建并激活环境

```bash

conda activate chatapi

python -m pip install -U fastapi uvicorn httpx pydantic
```

### 2) 使用流媒体（SSE）

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "内容类型：application/json" \
  -d '{"provider":"ollama","messages":[{"role":"user","content":"一句话解释RAG"}],"max_tokens":128}'
```
