from fastapi.testclient import TestClient
from src.app.main import app

client = TestClient(app)

"""对 FastAPI 应用的 /chat/stream 流式接口进行的 SSE（Server-Sent Events）格式合规性测试
    验证：
        流式接口返回 200 状态码且 Content-Type 符合 SSE 标准（text/event-stream）；
        接口返回的 SSE 数据块严格遵循 SSE 协议格式（包含 event: 和 data: 行，且至少有一行 data:）；
        确保流式响应的格式能被前端 SSE 客户端正确解析，不会因格式错误导致前端无法处理。
"""

# 辅助函数 SSE块解析
def _iter_sse_blocks(resp, max_blocks: int = 8) -> list[str]:
    """
        收集以空行分隔的 SSE 数据块。
        每个 SSE 数据块必须以空行结尾，因此用 '\n\n' 分隔。
    """
    buf = ""
    blocks: list[str] = []

    for chunk in resp.iter_text():
        buf += chunk

        while "\n\n" in buf:
            block, buf = buf.split("\n\n", 1)
            block = block.strip("\n")
            if block.strip():
                blocks.append(block)
            if len(blocks) >= max_blocks:
                return blocks

    return blocks

# 核心验证函数
def test_sse_format_basic():
    payload = {
        "provider": "mock",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 16,
    }

    with client.stream("POST", "/chat/stream", json=payload) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")

        blocks = _iter_sse_blocks(r, max_blocks=6)

    assert len(blocks) >= 2

    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        # 必须有 event 行
        assert any(ln.startswith("event: ") for ln in lines), f"missing event line in block: {block}"
        # 必须有 data 行
        assert any(ln.startswith("data: ") for ln in lines), f"missing data line in block: {block}"

        # 允许 data 多行，但至少一行 data:
        data_lines = [ln for ln in lines if ln.startswith("data: ")]
        assert len(data_lines) >= 1