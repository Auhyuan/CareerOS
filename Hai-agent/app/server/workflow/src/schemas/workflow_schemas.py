from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.server.project.src.schemas.project_schemas import NodeResponse


class StageResultSaveRequest(BaseModel):
    """保存当前步骤节点阶段结果的参数。"""

    node_id: UUID
    result: dict
    result_summary: str | None = Field(default=None, max_length=5000)
    expected_version: int = Field(default=0, ge=0)


class StageResultSaveResponse(BaseModel):
    """阶段结果保存响应。"""

    saved: bool
    node_id: UUID
    result_version: int
    node_status: str
    can_advance: bool


class NodeAdvanceRequest(BaseModel):
    """用户确认进入下一步骤的参数。"""

    model_config = ConfigDict(extra="forbid")

    node_id: UUID
    expected_result_version: int = Field(ge=1)


class NodeAdvanceResponse(BaseModel):
    """节点推进后返回当前冻结节点和新节点。"""

    current_node_id: UUID
    next_node: NodeResponse
    reused_existing_node: bool = False
