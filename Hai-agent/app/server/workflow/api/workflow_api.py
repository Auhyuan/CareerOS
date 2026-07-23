from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.db.postgres import get_db_session
from app.common.schemas.result import Result
from app.server.auth.src.dependencies import CurrentUser
from app.server.workflow.src.schemas.workflow_schemas import (
    NodeAdvanceRequest,
    NodeAdvanceResponse,
    StageResultSaveRequest,
    StageResultSaveResponse,
)
from app.server.workflow.src.service.workflow_service import WorkflowService


router = APIRouter()
workflow_service = WorkflowService()
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post("/nodes/save-result", response_model=Result[StageResultSaveResponse], summary="保存阶段结果")
def save_stage_result(
    request: StageResultSaveRequest, current_user: CurrentUser, db: DbSession
) -> Result[StageResultSaveResponse]:
    """保存当前用户节点的通用 JSON 阶段结果。"""
    return Result.success(workflow_service.save_stage_result(db, current_user.user_id, request), msg="节点结果已保存")


@router.post("/nodes/advance", response_model=Result[NodeAdvanceResponse], summary="进入下一步骤")
def advance_node(
    request: NodeAdvanceRequest, current_user: CurrentUser, db: DbSession
) -> Result[NodeAdvanceResponse]:
    """由用户确认推进节点，并为下一阶段创建独立 Checkpoint 标识。"""
    return Result.success(workflow_service.advance_node(db, current_user.user_id, request), msg="已进入下一步骤")
