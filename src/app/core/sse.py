import json
from typing import Any

"""SSE多行data的标准规范
    普通的SSE的data是单行的，但如过要推送包含换行符的文本（多行回复，代码块），SSE规定：
        - 每行数据都要以data: 开头
        - 最终以空行结尾表示事件结束。
"""

# 统一数据为字符串（含 JSON 序列化）
def _to_text(data: Any) -> str:
    if isinstance(data, (dict, list)):
        data_str = json.dumps(data, ensure_ascii=False)
    elif data is None:
        data_str = ""
    else:
        data_str = str(data)
    return data_str

"""生成符合 SSE（Server-Sent Events）标准格式的字符串。

event 支持 message、error、done 等事件类型；data 必须是字符串，
dict/list 会在 `_to_text` 中序列化为 JSON。
"""
def sse_event(event: str, data: Any) -> str:
    text = _to_text(data)
    # data 可以是 str/dict/list
    lines = text.splitlines() or [""]
    data_lines = "".join([f"data: {line}\n" for line in lines])

    # SSE block ends with a blank line -> "\n\n"
    return f"event: {event}\n" + f"{data_lines}\n"
