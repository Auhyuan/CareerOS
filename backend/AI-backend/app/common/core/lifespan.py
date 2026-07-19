from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.common.db.postgres_db import check_postgres_health
from app.server.knowledge.src.services import knowledge_service


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期钩子。

    服务启动时执行基础设施健康检查；后续如果要加 Redis、向量库、定时任务，也统一放这里编排。
    """
    check_postgres_health()
    print("PostgreSQL 健康检查通过")
    await knowledge_service.startup()
    try:
        yield
    finally:
        # 统一关闭知识库模块持有的 HTTP 连接池与 Milvus 连接。
        await knowledge_service.close()
