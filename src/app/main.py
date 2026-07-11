from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)
from sqlalchemy import text

from src.app.api.auth import (
    router as auth_router,
)
from src.app.api.routes_chat import router as chat_router
from src.app.api.routes_demo import router as demo_router
from src.app.api.prompts.routes_prompts import router as prompts_router
from src.app.api.prompt.routes_prompt import router as prompt_router
from src.app.api.runs.routes_runs import router as run_router
from src.app.api.kb.routes_kb import router as kb_router
from src.app.api.openai_compat import (
    router as openai_compat_router,
)
from src.app.api.conversations import (
    router as conversations_router,
)
from src.app.api.usage import (
    router as usage_router,
)
from src.app.auth.dependency import (
    require_api_key,
)
from src.app.auth.http import (
    install_api_key_exception_handlers,
)
from src.app.limits.dependency import (
    enforce_request_limits,
)
from src.app.limits.http import (
    install_rate_limit_headers_middleware,
    install_request_rate_limit_handler,
)
from src.app.core.logging import install_logging_middleware, setup_logging
from src.app.db.session import (
    get_session_factory,
)

# # 项目启动时初始化日志
setup_logging()
# 创建一个 FastAPI 应用实例 app，这是整个后端服务的核心对象，所有的中间件、路由、配置都挂载在这个实例上；
app = FastAPI()
"""安装全局日志中间件
    作用：所有通过这个 app 处理的请求（包括 /health、/chat、/chat/stream）都会被中间件拦截，自动添加 trace ID 和耗时统计。
"""
install_logging_middleware(app)
install_api_key_exception_handlers(app)
install_request_rate_limit_handler(app)
install_rate_limit_headers_middleware(app)

"""定义健康检查接口
    运维 / 监控工具（如 Kubernetes、Prometheus）会定期调用这个接口，判断服务是否正常运行；
    如果接口返回 {"status": "ok"}，说明服务存活；如果返回错误 / 超时，说明服务异常，会触发告警或重启。
"""
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """公开 readiness probe，只检查数据库连接边界."""

    try:
        with (
            get_session_factory()()
            as session
        ):
            session.execute(
                text("SELECT 1")
            )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "not_ready",
                "message": (
                    "Database readiness "
                    "check failed"
                ),
            },
        ) from exc

    return {"status": "ready"}

"""整合聊天路由模块
实现路由模块化：把不同功能的接口（聊天、用户、订单等）拆分到不同文件，避免入口文件代码臃肿；
"""
# Public application route.
app.include_router(demo_router)

# Authentication verification route.
# auth_router 自身已经声明 require_api_key dependency。
app.include_router(
    auth_router,
    dependencies=[
        Depends(enforce_request_limits),
    ],
)

# Protected native and OpenAI-compatible APIs.
protected_dependencies = [
    Depends(require_api_key),
    Depends(enforce_request_limits),
]

app.include_router(
    chat_router,
    dependencies=protected_dependencies,
)
app.include_router(
    prompts_router,
    dependencies=protected_dependencies,
)
app.include_router(
    prompt_router,
    dependencies=protected_dependencies,
)
app.include_router(
    run_router,
    dependencies=protected_dependencies,
)
app.include_router(
    kb_router,
    dependencies=protected_dependencies,
)
app.include_router(
    openai_compat_router,
    dependencies=protected_dependencies,
)
app.include_router(
    conversations_router,
    dependencies=protected_dependencies,
)
app.include_router(
    usage_router,
    dependencies=protected_dependencies,
)
