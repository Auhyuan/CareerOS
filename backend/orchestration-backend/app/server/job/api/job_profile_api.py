from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.job_profile import JobProfileGenerateRequest
from app.server.job.src.schemas.response import JobMarketProfileResponse
from app.server.job.src.service import JobProfileService


router = APIRouter(prefix="/profiles")
job_profile_service = JobProfileService()


@router.post("/generate", response_model=Result[JobMarketProfileResponse], summary="生成岗位画像")
def generate_job_profile(
    request: JobProfileGenerateRequest,
    db: Session = Depends(get_postgres_engine),
):
    """
    根据画像类型生成并保存岗位画像。
    Args:
        request: 岗位画像类型及对应生成路线参数。
        db: 数据库会话。
    Returns:
        已保存的岗位画像。
    """
    profile = job_profile_service.generate_profile(db, request)
    return Result.success(profile)


@router.get("/{profile_id}", response_model=Result[JobMarketProfileResponse], summary="查询岗位画像详情")
def get_job_profile(profile_id: int, db: Session = Depends(get_postgres_engine)):
    """
    根据画像 ID 查询岗位画像详情。
    Args:
        profile_id: 岗位画像 ID。
        db: 数据库会话。
    Returns:
        岗位画像详情。
    """
    profile = job_profile_service.get_profile_detail(db, profile_id)
    if profile is None:
        raise BusinessException(code=404, msg="岗位画像不存在")
    return Result.success(profile)
