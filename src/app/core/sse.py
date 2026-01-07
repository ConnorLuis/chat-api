import json

"""生成符合 SSE（Server-Sent Events，服务器推送事件）标准格式的字符串
    event: 事件类型message(正常消息)\error(错误)\done(流式结束)
    data: 推送的数据（必须是字符串，JSON需序列化）
"""
def sse_event(event: str, data) -> str:
    # data 可以是 str/dict/list
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)

    # SSE 框架：event + data + blank line
    return f"event: {event}\ndata: {data}\n\n"