cat > README.md << 'EOF'
# chat-api

A minimal FastAPI chat service with:
- `/health` health check
- `/chat` sync chat (mock / ollama)
- `/chat/stream` streaming chat (mock / ollama)
- global middleware: `x-trace-id` + latency logging

## Requirements
- WSL2 Ubuntu (recommended) + conda env
- Python 3.10+
- (Optional) Ollama running on Windows

## Quick Start

### 1) Create & activate env
```bash
conda activate chatapi
python -m pip install -U fastapi uvicorn httpx pydantic
