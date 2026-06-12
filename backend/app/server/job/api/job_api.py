from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.request import JobDirectionSearchRequest, JobPostingSearchRequest
from app.server.job.src.schemas.response import (
    JobDirectionListResponse,
    JobDirectionResponse,
    JobMarketProfileResponse,
    JobPostingListResponse,
    JobPostingResponse,
    JobRawRecordResponse,
)
from app.server.job.src.service.job_service import JobService


router = APIRouter()
job_service = JobService()


@router.get("/health", response_model=Result[Any], summary="岗位库服务健康检查")
def job_health():
    """岗位库服务健康检查接口。"""
    return Result.success({"service": "job", "status": "ok"})


@router.post("/directions/search", response_model=Result[JobDirectionListResponse], summary="查询岗位方向列表")
def search_job_directions(request: JobDirectionSearchRequest, db: Session = Depends(get_postgres_engine)):
    """
    分页查询平台定义的岗位方向。

    Args:
        request: 岗位方向查询条件。
        db: 数据库会话。
    """
    result = job_service.list_directions(
        db,
        keyword=request.keyword,
        status=request.status,
        page=request.page,
        page_size=request.page_size,
    )
    return Result.success(result)


@router.get("/directions/{direction_id}", response_model=Result[JobDirectionResponse], summary="查询岗位方向详情")
def get_job_direction(direction_id: int, db: Session = Depends(get_postgres_engine)):
    """
    查询岗位方向详情。

    Args:
        direction_id: 岗位方向 ID。
        db: 数据库会话。
    """
    direction = job_service.get_direction_detail(db, direction_id)
    if direction is None:
        raise BusinessException(code=404, msg="岗位方向不存在")
    return Result.success(direction)


@router.get(
    "/directions/{direction_id}/profile",
    response_model=Result[JobMarketProfileResponse],
    summary="查询岗位方向聚合画像",
)
def get_job_direction_profile(direction_id: int, db: Session = Depends(get_postgres_engine)):
    """
    查询某个岗位方向的聚合画像。

    Args:
        direction_id: 岗位方向 ID。
        db: 数据库会话。
    """
    direction = job_service.get_direction_detail(db, direction_id)
    if direction is None:
        raise BusinessException(code=404, msg="岗位方向不存在")

    profile = job_service.get_profile_by_direction_id(db, direction_id)
    if profile is None:
        raise BusinessException(code=404, msg="岗位画像不存在")
    return Result.success(profile)


@router.post("/postings/search", response_model=Result[JobPostingListResponse], summary="查询岗位列表")
def search_job_postings(request: JobPostingSearchRequest, db: Session = Depends(get_postgres_engine)):
    """
    分页查询岗位库。

    Args:
        request: 岗位列表查询条件。
        db: 数据库会话。
    """
    result = job_service.list_postings(
        db,
        keyword=request.keyword,
        city=request.city,
        platform=request.platform,
        status=request.status,
        page=request.page,
        page_size=request.page_size,
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
        raise BusinessException(code=404, msg="岗位不存在")
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
