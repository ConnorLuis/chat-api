import time
import asyncio
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from src.app.core.logging import get_trace_id # 链路追踪ID
from src.app.llm.schemas import ChatRequest, ChatResponse # 请求/响应模型
from src.app.llm.engines import get_engine # 引擎工厂函数
from fastapi.responses import StreamingResponse # 流式响应（重复导入，可删除）
from src.app.core.sse import sse_event # SSE格式生成函数


# 创建一个路由实例，后续的接口都注册在这个实例上，方便模块化管理。
# APIRouter：FastAPI 的路由拆分工具，用于将接口按功能分组
router = APIRouter()


# 普通的同步聊天接口
# 从请求的消息列表中提取用户最后一次发送的内容，拼接成模拟回复返回。
@router.post("/chat", response_model=ChatResponse)
def chat(req: Request, body: ChatRequest):
    # 从请求上下文获取trace ID（链路追踪）
    trace_id = get_trace_id(req)
    # 请求中的provider（mock/ollama）获取对应引擎实例
    engine = get_engine(body.provider)

    try:
        # 调用引擎的非流式generate方法生成回复（Mock返回模拟内容，Ollama调用真实模型）
        answer = engine.generate(body.messages, body.temperature, body.top_p, body.max_tokens)
    except Exception as e:
        # 捕获异常，返回502错误（网关错误），携带trace_id方便排查
        raise HTTPException(status_code=502, detail={"trace_id": trace_id, "error": f"{engine.name} failed: {str(e)}"})

    # 返回符合ChatResponse模型的响应
    return ChatResponse(trace_id=trace_id, session_id=body.session_id, answer=answer)

"""实现了标准化、可监控、可异常处理的 SSE 流式响应
    标准化的SSE响应：
        - 事件类型区分：meta初始化、token回复内容、usage统计、done结束、error异常。前端可按类型异常差异化处理
        - 数据格式统一：所有事件都通过sse_event生成，符合SSE标准，避免前端解析异常
    可监控：
        - 链路追踪：全流程携带 trace_id，日志 / 错误 / 统计都包含，便于定位问题；
        - 性能统计：记录耗时、token 数，可分析接口性能瓶颈；
        - 日志打印：后端输出关键指标，便于运维监控。
    兼容性与鲁棒性：
        - 引擎兼容：同时支持 Mock/Ollama 引擎，Mock 用于测试，Ollama 用于真实场景；
        - 异常兜底：所有异常都捕获并推送 error 事件，避免接口崩溃；
        - 边界处理：getattr(engine, "model", None) 兼容无 model 属性的引擎。
    前后端协同：
        - 前端可通过 meta 事件提前初始化；
        - token 事件实现打字机效果；
        - done 事件告知结束；
        - error 事件精准展示错误，提升用户体验。
"""
# 流式响应的异步聊天接口
@router.post("/chat/stream")
async def chat_stream(req: Request, body: ChatRequest):
    # 从请求上下文获取trace ID（链路追踪）
    trace_id = get_trace_id(req)
    # 请求中的provider（mock/ollama）获取对应引擎实例
    engine = get_engine(body.provider)

    # 定义异步生成器函数（核心：逐段产生响应数据）
    async def gen():
        start = time.perf_counter() # 记录开始时间（统计耗时）
        token_count = 0 # 统计返回的token数量

        # 把 trace / provider 发出去，前端好做初始化
        yield sse_event("meta", {"trace_id": trace_id, "provider": engine.name})

        try:
            # 调用引擎的stream方法（异步迭代器），逐token获取回复
            async for token in engine.stream(body.messages, body.temperature, body.top_p, body.max_tokens):
                token_count += 1 # 统计token数
                yield sse_event("token", token) # 推送token事件，逐段返回数据给前端

            # 计算耗时（毫秒）
            latency_ms = int((time.perf_counter() - start) * 1000)

            # 推送使用统计（usage事件）：包含性能、模型、token数等
            usage = {
                "trace_id": trace_id,
                "provider": engine.name,
                "model": getattr(engine, "model", None),
                "latency_ms": latency_ms,
                "token_events": token_count,
            }
            yield sse_event("usage", usage)
            yield sse_event("done", "[DONE]") # 推送结束事件，前端停止接收

            # 打印日志：便于后端监控
            print(f"[stream] trace={trace_id} provider={engine.name} model={usage['model']} latency_ms={latency_ms} token_events={token_count}")

        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            err = {
                "trace_id": trace_id,
                "provider": engine.name,
                "model": getattr(engine, "model", None),
                "latency_ms": latency_ms,
                "error": f"{engine.name} failed: {str(e)}",
            }
            # 异常时返回带trace_id的错误信息
            yield sse_event("error", err)

    # 返回流式响应，指定媒体类型为纯文本
    return StreamingResponse(gen(), media_type="text/event-stream")
