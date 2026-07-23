from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.common.db.postgres import get_db_session
from app.common.schemas.result import Result
from app.server.auth.src.dependencies import CurrentUser
from app.server.workflow.src.client import get_ai_backend_agent_client
from app.server.workflow.src.schemas.workflow_schemas import (
    BranchCreateRequest,
    BranchCreateResponse,
    NodeAdvanceRequest,
    NodeAdvanceResponse,
    NodeAgentMessageRequest,
    NodeAgentMessageResponse,
    StageResultSaveRequest,
    StageResultSaveResponse,
)
from app.server.workflow.src.service import NodeAgentService, WorkflowService


router = APIRouter()
workflow_service = WorkflowService()
node_agent_service = NodeAgentService()
ai_backend_agent_client = get_ai_backend_agent_client()
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "/nodes/messages",
    response_model=Result[NodeAgentMessageResponse],
    summary="向当前步骤 Agent 发送消息",
)
async def send_node_agent_message(
    request: NodeAgentMessageRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Result[NodeAgentMessageResponse] | StreamingResponse:
    """校验节点归属，注入动态上下文并调用当前阶段 Agent。"""
    prepared = node_agent_service.prepare_message(db, current_user.user_id, request)

    # Agent 运行可能持续数分钟。上下文已经复制到普通字典后立即结束读取事务，
    # 避免在 SSE 生命周期内长期占用 PostgreSQL 连接和事务快照。
    db.rollback()

    if request.stream:
        return StreamingResponse(
            ai_backend_agent_client.stream_message(prepared.payload),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Hai-Node-Id": str(prepared.node_id),
                "X-Hai-Conversation-Id": prepared.conversation_id,
            },
        )

    upstream_data = await ai_backend_agent_client.run_message(prepared.payload)
    response = NodeAgentMessageResponse(
        node_id=prepared.node_id,
        agent_id=prepared.agent_id,
        conversation_id=prepared.conversation_id,
        run_id=str(upstream_data.get("run_id") or ""),
        answer=str(upstream_data.get("answer") or ""),
        tool_results=(
            upstream_data.get("tool_results")
            if isinstance(upstream_data.get("tool_results"), list)
            else []
        ),
    )
    return Result.success(response, msg="Agent 执行完成")


@router.post("/nodes/save-result", response_model=Result[StageResultSaveResponse], summary="保存阶段结果")
def save_stage_result(
    request: StageResultSaveRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Result[StageResultSaveResponse]:
    """保存当前用户节点的通用 JSON 阶段结果。"""
    result = workflow_service.save_stage_result(db, current_user.user_id, request)
    return Result.success(result, msg="节点结果已保存")


@router.post(
    "/branches/create",
    response_model=Result[BranchCreateResponse],
    summary="从历史节点创建新分支",
)
def create_branch_from_node(
    request: BranchCreateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Result[BranchCreateResponse]:
    """复制历史节点业务基线，并创建使用独立 Checkpoint 的新分支节点。"""
    result = workflow_service.create_branch_from_node(db, current_user.user_id, request)
    return Result.success(result, msg="新分支已创建")


@router.post("/nodes/advance", response_model=Result[NodeAdvanceResponse], summary="进入下一步骤")
def advance_node(
    request: NodeAdvanceRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Result[NodeAdvanceResponse]:
    """由用户确认推进节点，并为下一阶段创建独立 Checkpoint 标识。"""
    result = workflow_service.advance_node(db, current_user.user_id, request)
    return Result.success(result, msg="已进入下一步骤")
