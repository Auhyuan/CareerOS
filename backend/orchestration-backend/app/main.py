import os
import sys
from pathlib import Path


# 支持在 orchestration-backend 目录下直接执行：python app/main.py。
# 直接按文件运行时，Python 默认只会把 orchestration-backend/app 加入 sys.path；
# 这里手动补上 orchestration-backend 根目录，保证 from app.xxx import xxx 可以正常工作。
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


def create_app() -> FastAPI:
    """
    创建编排层 FastAPI 应用实例。

    编排层负责就业平台业务流程，例如岗位数据入库、岗位画像生成和后续简历分析编排。

    Returns:
        已经完成中间件、异常处理器和业务编排路由注册的 FastAPI 应用。
    """
    app = FastAPI(lifespan=app_lifespan)

    # 当前阶段由 Java 侧做权限管理，编排层只负责业务流程执行，所以先允许跨域调用。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册全局异常处理器，让所有接口错误都返回统一 code/msg/data 结构。
    register_exception_handlers(app)

    # 编排层只挂载业务模块；Agent 和 Spider 由 capability-backend 提供。
    app.include_router(job_router, prefix="/job", tags=["job编排"])

    @app.get("/")
    def root_endpoint():
        """
        编排层健康检查入口。

        Returns:
            当前编排层服务的基础状态。
        """
        return Result.success({"message": "orchestration-backend", "status": "ok"})

    return app


def print_routes(app: FastAPI) -> None:
    """
    打印当前注册路由，方便本地启动时确认模块是否正常挂载。

    Args:
        app: FastAPI 应用实例。
    """
    print("当前 orchestration-backend 已注册路由列表：")
    for route in app.routes:
        if hasattr(route, "path"):
            print(route.path)
        else:
            print(f"  {route} - {type(route)}")


def print_startup_banner() -> None:
    """
    打印编排层启动横幅，让终端日志中可以一眼区分当前启动的是哪个服务。

    Returns:
        None。
    """
    host = os.getenv("FASTAPI_HOST", "127.0.0.1")
    port = os.getenv("FASTAPI_PORT", "8091")
    capability_base_url = os.getenv("CAPABILITY_BASE_URL", "http://127.0.0.1:8090")
    print("\n" + "=" * 72)
    print("  业务编排层 orchestration-backend 启动中")
    print("=" * 72)
    print(f"  服务地址: http://{host}:{port}")
    print(f"  能力层地址: {capability_base_url}")
    print("  服务职责: 岗位库 / 岗位画像 / 业务流程编排 / 数据入库")
    print("  对外模块: /job")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    app = create_app()
    print_startup_banner()
    print_routes(app)

    uvicorn.run(
        "app.main:create_app",
        host=os.getenv("FASTAPI_HOST", "127.0.0.1"),
        port=int(os.getenv("FASTAPI_PORT", 8091)),
        loop="asyncio",
        workers=1,
        reload=True,
        factory=True,
    )
