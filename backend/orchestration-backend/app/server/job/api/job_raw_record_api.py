from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.request import JobRawRecordSearchRequest
from app.server.job.src.schemas.response import JobRawRecordListResponse, JobRawRecordResponse
from app.server.job.src.service import JobRawRecordService


router = APIRouter(prefix="/raw-records")
job_raw_record_service = JobRawRecordService()


@router.post("/search", response_model=Result[JobRawRecordListResponse], summary="查询原始岗位列表")
def search_job_raw_records(request: JobRawRecordSearchRequest, db: Session = Depends(get_postgres_engine)):
    """
    分页查询招聘平台采集来的原始岗位池。
    Args:
        request: 原始岗位查询条件。
        db: 数据库会话。
    Returns:
        原始岗位分页列表。
    """
    result = job_raw_record_service.list_raw_records(
        db,
        keyword=request.keyword,
        city=request.city,
        platform=request.platform,
        page=request.page,
        page_size=request.page_size,
    )
    return Result.success(result)


@router.get("/{raw_record_id}", response_model=Result[JobRawRecordResponse], summary="查询原始岗位详情")
def get_job_raw_record(raw_record_id: int, db: Session = Depends(get_postgres_engine)):
    """
    根据原始岗位记录 ID 查询招聘平台原始数据详情。
    Args:
        raw_record_id: 原始岗位记录 ID。
        db: 数据库会话。
    Returns:
        原始岗位详情。
    """
    raw_record = job_raw_record_service.get_raw_record_detail(db, raw_record_id)
    if raw_record is None:
        raise BusinessException(code=404, msg="原始岗位记录不存在")
    return Result.success(raw_record)
