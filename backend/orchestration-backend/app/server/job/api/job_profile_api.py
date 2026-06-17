from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.response import JobMarketProfileResponse
from app.server.job.src.service import JobDirectionService, JobProfileService


router = APIRouter()
job_direction_service = JobDirectionService()
job_profile_service = JobProfileService()


@router.get("/directions/{direction_id}/profile", response_model=Result[JobMarketProfileResponse], summary="查询岗位方向画像")
def get_job_direction_profile(direction_id: int, db: Session = Depends(get_postgres_engine)):
    """
    查询某个岗位方向对应的平台岗位画像。
    Args:
        direction_id: 岗位方向 ID。
        db: 数据库会话。
    Returns:
        岗位画像详情。
    """
    direction = job_direction_service.get_direction_detail(db, direction_id)
    if direction is None:
        raise BusinessException(code=404, msg="岗位方向不存在")

    profile = job_profile_service.get_profile_by_direction_id(db, direction_id)
    if profile is None:
        raise BusinessException(code=404, msg="岗位画像不存在")
    return Result.success(profile)


@router.post("/profiles/generate", response_model=Result[dict[str, Any]], summary="生成岗位画像，占位接口")
def generate_job_profile_placeholder():
    """
    岗位画像生成占位接口。
    后续这里会统一承载岗位画像生成流程：查询岗位方向、筛选原始岗位样本、调用能力层 Agent、
    校验结构化结果，并把最终画像写入 job_market_profiles。
    Returns:
        当前占位状态。
    """
    return Result.success(
        {
            "status": "planned",
            "message": "岗位画像生成流程尚未实现，当前接口仅作为岗位画像 API 占位。",
        }
    )
