import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap import configure_logging
from app.common.config.settings import get_settings
from app.common.core.exceptions import register_exception_handlers
from app.common.core.lifespan import app_lifespan
from app.common.schemas.result import Result
from app.server.auth.api import router as auth_router
from app.server.project.api import router as project_router
from app.server.workflow.api import router as workflow_router


def create_app() -> FastAPI:
    """创建并组装 Hai-agent FastAPI 应用。"""
    configure_logging()
    settings = get_settings()
    application = FastAPI(
        title="Hai-agent API",
        description="活动策划多阶段智能体业务后端",
        lifespan=app_lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(auth_router, prefix="/auth", tags=["用户认证"])
    application.include_router(project_router, prefix="/projects", tags=["项目管理"])
    application.include_router(workflow_router, prefix="/workflow", tags=["工作流"])

    @application.get("/", response_model=Result[dict], summary="服务健康信息")
    def root_endpoint() -> Result[dict]:
        """返回不依赖鉴权的基础服务状态。"""
        return Result.success({"service": settings.app_name, "status": "ok"})

    return application


def print_startup_banner() -> None:
    """在本地启动时打印清晰的服务地址和模块信息。"""
    settings = get_settings()
    print("=" * 72)
    print(f"Hai-agent 后端启动: http://{settings.app_host}:{settings.app_port}")
    print("公开模块: /auth、/projects、/workflow")
    print("接口文档: /docs")
    print("=" * 72)


if __name__ == "__main__":
    settings = get_settings()
    print_startup_banner()
    uvicorn.run(
        "app.main:create_app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_reload,
        factory=True,
    )
