import os
import sys
from pathlib import Path


# 支持在 capability-backend 目录下直接执行：python app/main.py。
# 直接按文件运行时，Python 默认只会把 capability-backend/app 加入 sys.path；
# 这里手动补上 capability-backend 根目录，保证 from app.xxx import xxx 可以正常工作。
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.bootstrap  # 初始化异步环境和 .env，必须在业务模块导入前执行。
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.core.exceptions import register_exception_handlers
from app.common.core.lifespan import app_lifespan
from app.common.schemas.result import Result
from app.server.agent.api import router as agent_router
from app.server.spider.api import router as spider_router


def create_app() -> FastAPI:
    """
    创建能力层 FastAPI 应用实例。

    能力层只挂载通用能力模块，例如 Agent、爬虫、模型和工具；不挂载 job 这类业务编排模块。

    Returns:
        已经完成中间件、异常处理器和能力模块路由注册的 FastAPI 应用。
    """
    app = FastAPI(lifespan=app_lifespan)

    # 当前阶段由 Java 侧做权限管理，能力层只负责提供可调用能力，所以先允许跨域调用。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册全局异常处理器，让所有接口错误都返回统一 code/msg/data 结构。
    register_exception_handlers(app)

    # 能力层只挂载通用能力：Agent 和 Spider。
    app.include_router(spider_router, prefix="/spider", tags=["spider能力"])
    app.include_router(agent_router, prefix="/agent", tags=["agent能力"])

    @app.get("/")
    def root_endpoint():
        """
        能力层健康检查入口。

        Returns:
            当前能力层服务的基础状态。
        """
        return Result.success({"message": "capability-backend", "status": "ok"})

    return app


def print_routes(app: FastAPI) -> None:
    """
    打印当前注册路由，方便本地启动时确认模块是否正常挂载。

    Args:
        app: FastAPI 应用实例。
    """
    print("当前 capability-backend 已注册路由列表：")
    for route in app.routes:
        if hasattr(route, "path"):
            print(route.path)
        else:
            print(f"  {route} - {type(route)}")


def print_startup_banner() -> None:
    """
    打印能力层启动横幅，让终端日志中可以一眼区分当前启动的是哪个服务。

    Returns:
        None。
    """
    host = os.getenv("FASTAPI_HOST", "127.0.0.1")
    port = os.getenv("FASTAPI_PORT", "8090")
    print("\n" + "=" * 72)
    print("  基础能力层 capability-backend 启动中")
    print("=" * 72)
    print(f"  服务地址: http://{host}:{port}")
    print("  服务职责: Agent / Spider / Model / Tool 等通用能力")
    print("  对外模块: /agent, /spider")
    print("  注意事项: 爬虫能力只采集数据，不直接写岗位业务库")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    app = create_app()
    print_startup_banner()
    print_routes(app)

    uvicorn.run(
        "app.main:create_app",
        host=os.getenv("FASTAPI_HOST", "127.0.0.1"),
        port=int(os.getenv("FASTAPI_PORT", 8090)),
        loop="asyncio",
        workers=1,
        reload=True,
        factory=True,
    )
