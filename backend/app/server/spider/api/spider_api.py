from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.spider.src.schemas.request import QcwyJobCrawlRequest
from app.server.spider.src.schemas.response import SpiderCrawlResponse
from app.server.spider.src.service.spider_service import SpiderService


router = APIRouter()
spider_service = SpiderService()


@router.get("/health", response_model=Result[Any], summary="爬虫服务健康检查")
def spider_health():
    """爬虫服务健康检查接口。"""
    return Result.success({"service": "spider", "status": "ok"})


@router.post("/qcwy/jobs", response_model=Result[SpiderCrawlResponse], summary="采集前程无忧岗位")
def crawl_qcwy_jobs(request: QcwyJobCrawlRequest, db: Session = Depends(get_postgres_engine)):
    """
    采集前程无忧岗位信息。

    Args:
        request: 前程无忧岗位采集请求参数。
        db: 数据库会话。
    """
    result = spider_service.crawl_qcwy_jobs(request, db)
    return Result.success(result)
