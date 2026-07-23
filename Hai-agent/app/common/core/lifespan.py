from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.common.config.settings import get_settings
from app.common.db.postgres import check_postgres_health


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """管理应用启动和关闭，并在启动阶段检查关键依赖。"""
    settings = get_settings()
    insecure_secrets = {"change-this-secret-before-startup", "replace-with-a-long-random-secret"}
    if settings.jwt_secret_key in insecure_secrets or len(settings.jwt_secret_key) < 32:
        raise RuntimeError("JWT_SECRET_KEY 尚未安全配置，请在 .env 中设置至少 32 字节的随机值")
    check_postgres_health()
    print(f"PostgreSQL 健康检查通过: database={settings.postgres_database}, schema={settings.postgres_schema}")

    # FastAPI 不会自动执行挂载子应用的 lifespan。这里显式启动 FastMCP
    # Streamable HTTP 会话管理器，避免首次调用 /mcp 时出现 500。
    async with AsyncExitStack() as stack:
        mcp_app: Any | None = getattr(app.state, "mcp_app", None)
        mcp_lifespan = getattr(mcp_app, "lifespan", None) if mcp_app is not None else None
        if mcp_lifespan is not None:
            await stack.enter_async_context(mcp_lifespan(mcp_app))
            print("Hai-agent MCP 服务生命周期已启动")
        yield
