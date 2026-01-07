开始新对话前：“继续 chat-api 计划，从 Day？ 开始。”
# HANDOFF（给新对话用）
- 环境：WSL2 Ubuntu + conda env=chatapi (Python 3.10)
- 项目：~/projects/chat-api （GitHub: ConnorLuis/chat-api，branch master）
- Day1：/health OK
- Day2：/chat（mock + schemas）、全局中间件（x-trace-id + latency log）、/chat/stream OK
- Day3：可插拔引擎 LLMEngine（mock/ollama）；ChatRequest 增加 provider=mock|ollama
- Ollama：安装在 Windows，模型 qwen2.5:7b(Q4_K_M) 已 pull
- WSL 访问 Windows Ollama：export OLLAMA_BASE_URL="http://<WSL resolv.conf nameserver IP>:11434"
- 当前状态：provider=mock 和 provider=ollama 的 /chat 都已验收通过
- 下一步：Day4（稳定性、chat template、SSE、错误处理、测试/README/部署）
