import os
import sys
from pathlib import Path


# 支持从 backend 目录下直接执行：python app/main.py。
# 直接按文件运行时，Python 默认只把 backend/app 加进 sys.path；
# 这里手动补上 backend 根目录，保证 from app.xxx import xxx 可以正常工作。
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
from app.server.job.api import router as job_router
from app.server.spider.api import router as spider_router


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例，并注册所有功能模块路由。"""
    app = FastAPI(lifespan=app_lifespan)

    # 当前阶段由 Java 侧做权限管理，这里只负责功能接口，所以先允许跨域调用。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册全局异常处理器，让所有接口错误都返回统一 code/msg/data 结构。
    register_exception_handlers(app)

    # 每个服务模块只通过自己的 api 聚合出口对外暴露接口。
    app.include_router(spider_router, prefix="/spider", tags=["spider模块"])
    app.include_router(job_router, prefix="/job", tags=["job模块"])

    @app.get("/")
    def root_endpoint():
        """统一入口健康检查。"""
        return Result.success({"message": "统一入口"})

    return app


def print_routes(app: FastAPI) -> None:
    """
    打印当前注册路由，方便本地启动时确认模块是否正常挂载。

    Args:
        app: FastAPI 应用实例。
    """
    print("当前 FastAPI 已注册路由列表：")
    for route in app.routes:
        if hasattr(route, "path"):
            print(route.path)
        else:
            print(f"  {route} - {type(route)}")


if __name__ == "__main__":
    app = create_app()
    print_routes(app)

    uvicorn.run(
        "app.main:create_app",
        host=os.getenv("FastApi_host", "127.0.0.1"),
        port=int(os.getenv("FastApi_port", 8090)),
        loop="asyncio",
        workers=1,
        reload=True,
        factory=True,
    )
