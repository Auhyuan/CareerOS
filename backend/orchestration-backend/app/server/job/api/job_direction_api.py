from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.request import JobDirectionSearchRequest
from app.server.job.src.schemas.response import JobDirectionListResponse, JobDirectionResponse
from app.server.job.src.service import JobDirectionService


router = APIRouter(prefix="/directions")
job_direction_service = JobDirectionService()


@router.post("/search", response_model=Result[JobDirectionListResponse], summary="查询岗位方向列表")
def search_job_directions(request: JobDirectionSearchRequest, db: Session = Depends(get_postgres_engine)):
    """
    分页查询平台定义的岗位方向。

    Args:
        request: 岗位方向查询条件。
        db: 数据库会话。

    Returns:
        岗位方向分页列表。
    """
    result = job_direction_service.list_directions(
        db,
        keyword=request.keyword,
        status=request.status,
        page=request.page,
        page_size=request.page_size,
    )
    return Result.success(result)


@router.get("/{direction_id}", response_model=Result[JobDirectionResponse], summary="查询岗位方向详情")
def get_job_direction(direction_id: int, db: Session = Depends(get_postgres_engine)):
    """
    查询岗位方向详情。

    Args:
        direction_id: 岗位方向 ID。
        db: 数据库会话。

    Returns:
        岗位方向详情。
    """
    direction = job_direction_service.get_direction_detail(db, direction_id)
    if direction is None:
        raise BusinessException(code=404, msg="岗位方向不存在")
    return Result.success(direction)
