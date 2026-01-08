import json
from typing import Any

"""SSE多行data的标准规范
    普通的SSE的data是单行的，但如过要推送包含换行符的文本（多行回复，代码块），SSE规定：
        - 每行数据都要以data: 开头
        - 最终以空行结尾表示事件结束。
"""

# 统一数据为字符串（含 JSON 序列化）
def _to_text(data: Any) -> str:
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False)

"""生成符合 SSE（Server-Sent Events，服务器推送事件）标准格式的字符串
    event: 事件类型message(正常消息)\error(错误)\done(流式结束)
    data: 推送的数据（必须是字符串，JSON需序列化）
"""
def sse_event(event: str, data: Any) -> str:
    text = _to_text(data)
    # data 可以是 str/dict/list
    lines = text.splitlines() or [""]
    data_lines = "".join([f"data: {line}\n" for line in lines])

    # SSE 框架：event + data + blank line
    return f"event: {event}\n{data_lines}\n"