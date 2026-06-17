from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.common.db.postgres_db import check_postgres_health


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期钩子。

    服务启动时执行基础设施健康检查；后续如果要加 Redis、向量库、定时任务，也统一放这里编排。
    """
    check_postgres_health()
    print("PostgreSQL 健康检查通过")
    yield
