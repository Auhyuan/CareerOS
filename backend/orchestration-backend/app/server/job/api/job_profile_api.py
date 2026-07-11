from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.job_profile import (
    JobProfileBatchDeleteRequest,
    JobProfileBatchDeleteResponse,
    JobProfileGenerateRequest,
    UserJobProfileSearchRequest,
)
from app.server.job.src.schemas.response import (
    JobMarketProfileListResponse,
    JobMarketProfileResponse,
    JobProfileGenerateResponse,
)
from app.server.job.src.service import JobProfileService


router = APIRouter(prefix="/profiles")
job_profile_service = JobProfileService()


@router.post("/generate", response_model=Result[JobProfileGenerateResponse], summary="生成岗位画像")
def generate_job_profile(request: JobProfileGenerateRequest):
    """调用岗位画像 Agent 生成并保存岗位画像。

    岗位画像由 Agent 在执行过程中调用 save_job_profile 工具写入数据库。
    本接口不再解析 Agent JSON，也不会执行第二次入库。

    Args:
        request: 岗位画像类型及对应生成路线参数。

    Returns:
        Agent 运行 ID 和最终回复。
    """
    result = job_profile_service.generate_profile(request)
    return Result.success(result)


@router.post("/search", response_model=Result[JobMarketProfileListResponse], summary="根据用户 ID 查询岗位画像列表")
def search_user_job_profiles(
    request: UserJobProfileSearchRequest,
    db: Session = Depends(get_postgres_engine),
):
    """
    根据用户 ID 分页查询该用户生成的岗位画像。

    Args:
        request: 用户 ID 和分页参数。
        db: 数据库会话。

    Returns:
        用户岗位画像分页列表。
    """
    result = job_profile_service.list_user_profiles(
        db,
        user_id=request.user_id,
        page=request.page,
        page_size=request.page_size,
    )
    return Result.success(result)


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


@router.delete("/{profile_id}", response_model=Result[None], summary="根据画像 ID 删除岗位画像")
def delete_job_profile(profile_id: int, db: Session = Depends(get_postgres_engine)):
    """
    根据画像 ID 删除岗位画像。画像不存在时返回 404。

    Args:
        profile_id: 岗位画像 ID。
        db: 数据库会话。

    Returns:
        空数据的成功响应。
    """
    job_profile_service.delete_profile(db, profile_id)
    return Result.success(msg="岗位画像已删除")


@router.post("/delete", response_model=Result[JobProfileBatchDeleteResponse], summary="批量删除岗位画像")
def delete_job_profiles(
    request: JobProfileBatchDeleteRequest,
    db: Session = Depends(get_postgres_engine),
):
    """
    根据画像 ID 列表批量删除岗位画像。

    请求中不存在的 ID 不会抛错，会一起返回到 missing_ids，便于前端提示。

    Args:
        request: 批量删除请求，包含去重后的画像 ID 列表。
        db: PostgreSQL 数据库会话。

    Returns:
        统一响应结构，data 中包含已删除 / 缺失的画像 ID 统计信息。
    """
    result = job_profile_service.delete_profiles(db, request)
    return Result.success(result)
