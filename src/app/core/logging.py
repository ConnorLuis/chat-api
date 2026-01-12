import logging
import time
import uuid
from fastapi import FastAPI, Request

# 定义 trace ID 在HTTP头中的键名，用于在请求 / 响应头中传递 trace ID
TRACE_ID_HEADER = "x-trace-id"

# 初始化业务专属日志器（全局唯一）
logger = logging.getLogger("llm_chat_log")

# 从请求对象中获取 trace ID
def get_trace_id(req: Request) -> str:
    # 在接口处理函数中，可以通过这个函数快速获取当前请求的 trace ID，方便日志记录、业务逻辑关联等。
    return getattr(req.state, "trace_id", "no-trace")

"""日志中间件安装函数
    FastAPI 的 middleware("http") 是全局 HTTP 中间件，会拦截所有的 HTTP 请求和响应，执行顺序是：
    客户端请求 → 中间件前置逻辑 → 接口处理函数 → 中间件后置逻辑 → 客户端响应
"""
def install_logging_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_trace_and_timing(request: Request, call_next):
        # 生成或获取 trace ID
        # 优先从请求头中取 x-trace-id（比如客户端传递的），没有则生成 UUID 作为 trace ID
        trace_id = request.headers.get(TRACE_ID_HEADER) or str(uuid.uuid4())
        # 将 trace ID 存入请求上下文，供后续接口逻辑使用
        request.state.trace_id = trace_id

        # 记录请求开始时间（秒级时间戳）
        t0 = time.time()
        # 执行后续逻辑（调用接口处理函数，获取响应）
        response = await  call_next(request)
        # 计算请求耗时（转换为毫秒，保留1位小数）
        cost_ms = (time.time() - t0) * 1000

        # 将 trace ID 写入响应头，让客户端能拿到这个 ID（方便排查问题）
        response.headers[TRACE_ID_HEADER] = trace_id
        # 打印结构化日志，包含关键信息
        logger.info(f"[trace={trace_id}] {request.method} {request.url.path} {response.status_code} {cost_ms:.1f}ms")
        # 返回响应给客户端
        return response

# 封装日志配置逻辑，项目启动时调用一次即可完成全局日志初始化
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        # 定义日志输出格式
        # 日志记录时间-日志器名称-日志级别名称-日志核心内容
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        # 指定日志输出目标
        handlers=[
            logging.StreamHandler()
        ]
    )