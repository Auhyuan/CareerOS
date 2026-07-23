from contextlib import asynccontextmanager

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
    yield
