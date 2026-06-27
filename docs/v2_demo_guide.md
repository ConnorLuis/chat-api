# chat-api v2 Demo Guide

## 1. Demo 目标

本文档用于演示 `chat-api` v2 的完整能力链路。它不是系统设计说明，而是一份可以按顺序执行的演示脚本。

演示目标：

```text
1. 服务启动与健康检查；
2. 同步 /chat；
3. 流式 /chat/stream；
4. RAG 同步问答；
5. Hybrid RAG metadata；
6. Prompt Compare；
7. Run Replay；
8. RAG eval workflow；
9. 运行时产物清理。