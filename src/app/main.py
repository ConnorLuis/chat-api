from fastapi import FastAPI

from src.app.api.routes_chat import router as chat_router
from src.app.core.logging import install_logging_middleware

# 创建一个 FastAPI 应用实例 app，这是整个后端服务的核心对象，所有的中间件、路由、配置都挂载在这个实例上；
app = FastAPI()
"""安装全局日志中间件
    作用：所有通过这个 app 处理的请求（包括 /health、/chat、/chat/stream）都会被中间件拦截，自动添加 trace ID 和耗时统计。
"""
install_logging_middleware(app)

"""定义健康检查接口
    运维 / 监控工具（如 Kubernetes、Prometheus）会定期调用这个接口，判断服务是否正常运行；
    如果接口返回 {"status": "ok"}，说明服务存活；如果返回错误 / 超时，说明服务异常，会触发告警或重启。
"""
@app.get("/health")
def health():
    return {"status": "ok"}

"""整合聊天路由模块
实现路由模块化：把不同功能的接口（聊天、用户、订单等）拆分到不同文件，避免入口文件代码臃肿；
"""
app.include_router(chat_router)