from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.job_profile import TemporaryJobProfileGenerateRequest
from app.server.job.src.schemas.response import JobMarketProfileResponse
from app.server.job.src.service import JobProfileService


router = APIRouter(prefix="/profiles")
job_profile_service = JobProfileService()


@router.post("/generate", response_model=Result[JobMarketProfileResponse], summary="生成用户临时岗位画像")
def generate_temporary_job_profile(
    request: TemporaryJobProfileGenerateRequest,
    db: Session = Depends(get_postgres_engine),
):
    """
    根据用户提交的岗位文本生成并保存临时岗位画像。
    Args:
        request: 用户 ID、岗位文本和系统岗位数据参考开关。
        db: 数据库会话。
    Returns:
        已保存的临时岗位画像。
    """
    profile = job_profile_service.generate_temporary_profile(db, request)
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
