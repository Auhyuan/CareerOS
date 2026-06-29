from typing import Any

from fastapi import APIRouter

from app.common.schemas.result import Result
from app.server.spider.src.schemas.request import QcwyJobCrawlRequest
from app.server.spider.src.schemas.response import SpiderCrawlResponse
from app.server.spider.src.service.spider_service import SpiderService


router = APIRouter()
spider_service = SpiderService()


@router.get("/health", response_model=Result[Any], summary="爬虫能力健康检查")
def spider_health():
    """
    检查爬虫能力模块是否已经挂载。

    Returns:
        爬虫能力模块基础运行状态。
    """
    return Result.success({"service": "spider", "status": "ok"})


@router.post("/qcwy/jobs", response_model=Result[SpiderCrawlResponse], summary="采集前程无忧岗位")
def crawl_qcwy_jobs(request: QcwyJobCrawlRequest):
    """
    采集前程无忧岗位信息。

    能力层只负责采集和返回原始结果，不负责创建爬虫任务记录，也不负责写入岗位业务库。

    Args:
        request: 前程无忧岗位采集请求参数。

    Returns:
        采集结果，包含岗位行数据和可选文件输出路径。
    """
    result = spider_service.crawl_qcwy_jobs(request)
    return Result.success(result)
