from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.request import JobPostingSearchRequest
from app.server.job.src.schemas.response import JobPostingListResponse, JobPostingResponse, JobRawRecordResponse
from app.server.job.src.service import JobPostingService


router = APIRouter(prefix="/postings")
job_posting_service = JobPostingService()


@router.post("/search", response_model=Result[JobPostingListResponse], summary="查询岗位列表")
def search_job_postings(request: JobPostingSearchRequest, db: Session = Depends(get_postgres_engine)):
    """
    分页查询爬虫采集并标准化后的岗位主表。

    Args:
        request: 岗位列表查询条件。
        db: 数据库会话。

    Returns:
        岗位分页列表。
    """
    result = job_posting_service.list_postings(
        db,
        keyword=request.keyword,
        city=request.city,
        platform=request.platform,
        status=request.status,
        page=request.page,
        page_size=request.page_size,
    )
    return Result.success(result)


@router.get("/{job_id}", response_model=Result[JobPostingResponse], summary="查询岗位详情")
def get_job_posting(job_id: int, db: Session = Depends(get_postgres_engine)):
    """
    查询标准化岗位详情。

    Args:
        job_id: 岗位主表 ID。
        db: 数据库会话。

    Returns:
        标准化岗位详情。
    """
    job = job_posting_service.get_posting_detail(db, job_id)
    if job is None:
        raise BusinessException(code=404, msg="岗位不存在")
    return Result.success(job)


@router.get(
    "/{job_id}/raw-records",
    response_model=Result[list[JobRawRecordResponse]],
    summary="查询岗位原始采集记录",
)
def list_job_raw_records(job_id: int, limit: int = 20, db: Session = Depends(get_postgres_engine)):
    """
    查询某个标准化岗位最近的原始采集记录。

    Args:
        job_id: 岗位主表 ID。
        limit: 返回数量上限。
        db: 数据库会话。

    Returns:
        原始岗位采集记录列表。
    """
    records = job_posting_service.list_raw_records_by_job(db, job_id, limit=limit)
    return Result.success(records)
