from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.job.src.schemas.job_skill import (
    JobSkillBatchCreateRequest,
    JobSkillBatchCreateResponse,
    JobSkillBatchDeleteRequest,
    JobSkillBatchDeleteResponse,
    JobSkillCreateRequest,
    JobSkillCreateResponse,
    JobSkillSearchRequest,
    JobSkillSearchResponse,
)
from app.server.job.src.service.job_skill_service import JobSkillService


router = APIRouter(prefix="/skills")
job_skill_service = JobSkillService()


@router.post("/search", response_model=Result[JobSkillSearchResponse], summary="查询岗位技能")
def search_job_skills(
    request: JobSkillSearchRequest,
    db: Session = Depends(get_postgres_engine),
):
    """
    根据关键词查询平台岗位技能。

    Args:
        request: 技能查询关键字和返回数量。
        db: PostgreSQL 数据库会话。

    Returns:
        统一响应结构，data 中包含匹配技能列表。
    """
    result = job_skill_service.search_skills(db, request)
    return Result.success(result)


@router.post("/create", response_model=Result[JobSkillCreateResponse], summary="创建岗位技能")
def create_job_skill(
    request: JobSkillCreateRequest,
    db: Session = Depends(get_postgres_engine),
):
    """
    创建岗位技能；标准化名称已存在时直接返回已有技能。

    Args:
        request: 技能名称和技能描述。
        db: PostgreSQL 数据库会话。

    Returns:
        统一响应结构，data 中包含技能和是否新建的标记。
    """
    result = job_skill_service.create_skill(db, request)
    return Result.success(result)


@router.post("/batch-create", response_model=Result[JobSkillBatchCreateResponse], summary="批量创建岗位技能")
def batch_create_job_skills(
    request: JobSkillBatchCreateRequest,
    db: Session = Depends(get_postgres_engine),
):
    """
    批量创建岗位技能；标准化名称已存在时直接复用已有技能。

    Args:
        request: 批量技能创建请求。
        db: PostgreSQL 数据库会话。

    Returns:
        统一响应结构，data 中包含批量创建 / 复用结果。
    """
    result = job_skill_service.batch_create_skills(db, request)
    return Result.success(result)


@router.post("/delete", response_model=Result[JobSkillBatchDeleteResponse], summary="批量删除岗位技能")
def delete_job_skills(
    request: JobSkillBatchDeleteRequest,
    db: Session = Depends(get_postgres_engine),
):
    """
    根据技能 ID 列表批量删除岗位技能。

    请求中不存在的 ID 不会抛错，会一起返回到 missing_ids，便于前端提示。

    Args:
        request: 批量删除请求，包含去重后的技能 ID 列表。
        db: PostgreSQL 数据库会话。

    Returns:
        统一响应结构，data 中包含已删除 / 缺失的技能 ID 统计信息。
    """
    result = job_skill_service.delete_skills(db, request)
    return Result.success(result)
