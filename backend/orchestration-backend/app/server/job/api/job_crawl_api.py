from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.request import QcwyJobCrawlAndIngestRequest
from app.server.job.src.schemas.response import JobCrawlIngestResponse
from app.server.job.src.service import JobCrawlService


router = APIRouter(prefix="/crawl")
job_crawl_service = JobCrawlService()


@router.post("/qcwy/jobs", response_model=Result[JobCrawlIngestResponse], summary="采集并入库前程无忧岗位")
def crawl_and_ingest_qcwy_jobs(
    request: QcwyJobCrawlAndIngestRequest,
    db: Session = Depends(get_postgres_engine),
):
    """
    编排前程无忧岗位采集和入库。

    该接口属于 orchestration-backend：它调用 AI-backend 的爬虫能力，然后负责写入岗位业务库。

    Args:
        request: 前程无忧岗位采集并入库请求。
        db: 数据库会话。

    Returns:
        采集结果、爬虫运行记录 ID 和入库统计。
    """
    result = job_crawl_service.crawl_qcwy_jobs_and_ingest(db, request)
    return Result.success(result)
