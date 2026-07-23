from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.db.postgres import get_db_session
from app.common.schemas.result import Result
from app.server.auth.src.dependencies import CurrentUser
from app.server.project.src.schemas.project_schemas import (
    ProjectCreateRequest,
    ProjectDetailRequest,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectSearchRequest,
)
from app.server.project.src.service.project_service import ProjectService


router = APIRouter()
project_service = ProjectService()
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post("/create", response_model=Result[ProjectDetailResponse], summary="创建项目")
def create_project(
    request: ProjectCreateRequest, current_user: CurrentUser, db: DbSession
) -> Result[ProjectDetailResponse]:
    """为当前用户创建项目、主分支和项目准备根节点。"""
    return Result.success(project_service.create_project(db, current_user.user_id, request), msg="项目创建成功")


@router.post("/search", response_model=Result[ProjectListResponse], summary="查询项目列表")
def search_projects(
    request: ProjectSearchRequest, current_user: CurrentUser, db: DbSession
) -> Result[ProjectListResponse]:
    """仅查询当前登录用户拥有的项目。"""
    return Result.success(project_service.search_projects(db, current_user.user_id, request))


@router.post("/detail", response_model=Result[ProjectDetailResponse], summary="查询项目详情")
def get_project_detail(
    request: ProjectDetailRequest, current_user: CurrentUser, db: DbSession
) -> Result[ProjectDetailResponse]:
    """返回当前用户项目及其分支和节点树。"""
    return Result.success(project_service.get_project_detail(db, current_user.user_id, request.project_id))
