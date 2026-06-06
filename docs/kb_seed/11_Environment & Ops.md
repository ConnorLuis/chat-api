# Header

* Title：11_Environment & Ops（Configuration + Deployment + Troubleshooting）
* Source：kb_seed
* Scope：

  * 环境配置管理
  * 本地开发环境
  * WSL2 + Windows 联调
  * Ollama 接入
  * Chroma 持久化
  * 运行日志与目录规范
* Out of scope：

  * PromptHub（见 04）
  * RAG 原理（见 08）
  * KB Documents Management（见 09）
* Files：

  * `.env`
  * `src/app/core/config.py`
  * `src/app/core/settings.py`
  * `requirements.txt`
* Related Tests：

  * 配置加载测试
  * 环境变量覆盖测试
  * 健康检查测试

# TL;DR

* 所有运行参数优先来自环境变量。
* 开发环境默认通过 `.env` 管理配置。
* Ollama 可以部署在 Windows 主机，由 WSL2 中的 FastAPI 服务通过 HTTP 调用。
* Chroma 使用持久化目录保存向量数据。
* 所有关键目录应满足可恢复、可备份、可迁移要求。

# Why Environment & Ops

功能实现完成后，系统仍然需要能够稳定部署、维护和排障。

常见问题包括：

* 环境变量配置错误
* Ollama 地址变更
* Chroma 数据目录损坏
* 日志目录权限不足
* WSL2 与 Windows 网络地址变化

因此需要统一环境与运维规范。

# Configuration Strategy

配置优先级：

1. Environment Variables
2. `.env`
3. Code Default

常见配置项：

```text
OLLAMA_BASE_URL
OLLAMA_MODEL
CHROMA_PERSIST_DIR
RUN_LOG_DIR
LOG_LEVEL
```

应用启动时统一加载配置。

业务逻辑层不直接读取 `os.environ`。

统一由配置模块提供配置对象。
## Local Embedding Model Path（WSL 访问 Windows 本地模型）

如果 embedding 模型下载在 Windows 本地目录中，WSL 可以通过 `/mnt/<drive>/...` 访问。

例如 Windows 路径：

C:\Users\<user>\models\bce-embedding-base_v1
在 WSL 中对应：

```text
/mnt/c/Users/<user>/models/bce-embedding-base_v1
```

# Ollama Integration

推荐部署方式：

Windows：

```text
Ollama
↓
11434
```

WSL2：

```text
FastAPI
↓
http://<windows-host-ip>:11434
↓
Ollama
```

验证方式：

```bash
curl http://localhost:11434/api/tags
```

或者：

```bash
curl http://<windows-ip>:11434/api/tags
```

如果能够返回模型列表，则说明服务可用。

WSL2 中可通过：

cat /etc/resolv.conf | grep nameserver

获取 Windows Host IP。

例如：

OLLAMA_BASE_URL=http://172.29.96.1:11434

# Chroma Persistence

向量库必须使用持久化目录。

推荐：

```text
data/chroma/
```

持久化内容包括：

* Collection
* Embeddings
* Metadata

服务重启后可直接恢复。

无需重新执行 ingest。

如果需要完全重建向量库：

1. 删除 Chroma persist directory
2. 删除 docs.jsonl（可选）
3. 删除 docs/*.md（可选）
4. 重新执行 ingest

重建后所有 doc_id 会重新生成。

# Run Logs

运行日志建议单独存放：

```text
runs/
```

每次请求记录：

* trace_id
* provider
* latency_ms
* rag metadata
* citations

运行日志可用于：

* Replay
* 调试
* 审计
* 性能分析

# Deployment Checklist

启动前检查：

* Python 环境正确
* 依赖安装完成
* Ollama 已启动
* Chroma 目录存在
* docs.jsonl 可写
* runs 目录可写

启动后检查：

* `/health`
* `/chat`
* `/chat/stream`
* `/kb/search`

均能正常返回结果。

# Failure Modes

## Ollama 不可达

表现：

* Connection Refused
* Timeout

排查：

* 检查 OLLAMA_BASE_URL
* 检查 Ollama 是否运行
* 使用 curl 验证

## 配置错误

表现：

* 服务启动失败
* 配置项为空

排查：

* 检查环境变量
* 检查 .env 文件
* 检查配置加载顺序

## 文件权限问题

表现：

* docs.jsonl 无法写入
* Chroma 初始化失败
* run log 写入失败

排查：

* 检查目录权限
* 检查磁盘空间

## 数据问题

表现：

* 搜索结果为空
* Collection 丢失

排查：

* 检查 Chroma 目录
* 检查 Collection 是否存在
* 检查向量维度是否一致

# Tests Mapping

test_settings_load.py

验证：

* 默认配置加载
* 环境变量覆盖

test_health_contract.py

验证：

* 服务正常启动

test_ollama_connectivity.py

验证：

* Ollama 可访问

# Pitfalls & Debug Playbook

症状：

Ollama 调用失败

排查：

1. 检查 OLLAMA_BASE_URL
2. curl tags
3. 检查网络连通性

症状：

KB 搜索无结果

排查：

1. 检查 Chroma 数据目录
2. 检查 Collection 是否存在
3. 检查是否执行过 ingest

症状：

日志未生成

排查：

1. 检查 RUN_LOG_DIR
2. 检查目录权限
3. 检查磁盘空间

---

# Keywords

environment
ops
deployment
configuration
.env
ollama
wsl2
chroma
run logs
operations
settings
monitoring

# QA Seeds

Q: 配置优先级是什么？
A: Environment Variables > .env > Code Default

Q: Chroma 为什么需要持久化？
A: 避免服务重启后重新执行 ingest。

Q: WSL2 如何访问 Ollama？
A: 通过 Windows 主机暴露的 HTTP 地址访问。

Q: run logs 的作用是什么？
A: 用于 replay、调试、审计和性能分析。

Q: 部署前需要检查什么？
A: Python 环境、依赖、Ollama、Chroma、docs.jsonl 和 runs 目录。
