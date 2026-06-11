from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.response import (
    JobPostingListResponse,
    JobPostingResponse,
    JobRawRecordResponse,
)
from app.server.job.src.service.job_service import JobService


router = APIRouter()
job_service = JobService()


@router.get("/health", response_model=Result[Any], summary="岗位库服务健康检查")
def job_health():
    """
    岗位库服务健康检查接口。

    用于确认 job 服务模块已经被 FastAPI 正常注册。
    """
    return Result.success({"service": "job", "status": "ok"})


@router.get("/postings", response_model=Result[JobPostingListResponse], summary="查询岗位列表")
def list_job_postings(
    keyword: str | None = None,
    city: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_postgres_engine),
):
    """
    分页查询岗位库。

    Args:
        keyword: 岗位标题关键词。
        city: 城市筛选。
        platform: 平台筛选，例如 qcwy。
        status: 岗位状态筛选，例如 recruiting。
        page: 当前页码。
        page_size: 每页数量。
        db: 数据库会话。
    """
    result = job_service.list_postings(
        db,
        keyword=keyword,
        city=city,
        platform=platform,
        status=status,
        page=page,
        page_size=page_size,
    )
    return Result.success(result)


@router.get("/postings/{job_id}", response_model=Result[JobPostingResponse], summary="查询岗位详情")
def get_job_posting(job_id: int, db: Session = Depends(get_postgres_engine)):
    """
    查询岗位详情。

    Args:
        job_id: 岗位主表 ID。
        db: 数据库会话。
    """
    job = job_service.get_posting_detail(db, job_id)
    if job is None:
        return Result.fail(404, "岗位不存在")
    return Result.success(job)


@router.get(
    "/postings/{job_id}/raw-records",
    response_model=Result[list[JobRawRecordResponse]],
    summary="查询岗位原始采集记录",
)
def list_job_raw_records(job_id: int, limit: int = 20, db: Session = Depends(get_postgres_engine)):
    """
    查询某个岗位最近的原始采集记录。

    Args:
        job_id: 岗位主表 ID。
        limit: 返回数量上限。
        db: 数据库会话。
    """
    records = job_service.list_raw_records_by_job(db, job_id, limit=limit)
    return Result.success(records)
