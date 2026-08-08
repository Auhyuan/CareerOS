from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.server.project.src.schemas.project_schemas import BranchResponse, NodeResponse


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


class RootBranchCreateRequest(BaseModel):
    """从项目虚拟开始节点创建新根分支的参数。"""

    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    branch_name: str = Field(min_length=1, max_length=255)

    @field_validator("branch_name")
    @classmethod
    def normalize_branch_name(cls, value: str) -> str:
        """清理根分支名称两侧空白，并拒绝空白名称。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("branch_name 不能为空")
        return cleaned

class BranchCreateRequest(BaseModel):
    """从历史节点创建独立工作流分支的参数。"""

    model_config = ConfigDict(extra="forbid")

    source_node_id: UUID
    branch_name: str = Field(min_length=1, max_length=255)
    expected_result_version: int = Field(ge=1)

    @field_validator("branch_name")
    @classmethod
    def normalize_branch_name(cls, value: str) -> str:
        """清理分支名称两侧空白，并拒绝空白名称。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("branch_name 不能为空")
        return cleaned


class BranchCreateResponse(BaseModel):
    """历史节点派生分支的创建结果。"""

    branch: BranchResponse
    node: NodeResponse


class NodeConversationHistoryRequest(BaseModel):
    """查询工作流节点对应 Agent 会话历史的参数。"""

    model_config = ConfigDict(extra="forbid")

    node_id: UUID
    limit: int = Field(default=100, ge=1, le=200)


class NodeConversationMessage(BaseModel):
    """前端展示使用的节点 Agent 历史消息。"""

    message_id: str
    role: str
    message_type: str
    content: str | None = None
    structured_content: dict[str, Any] | None = None
    tool_name: str | None = None
    status: str = "success"
    error_message: str | None = None


class NodeConversationHistoryResponse(BaseModel):
    """节点 Agent 会话历史查询响应。"""

    node_id: UUID
    conversation_id: str
    messages: list[NodeConversationMessage] = Field(default_factory=list)


class NodeAgentMessageRequest(BaseModel):
    """向当前工作流节点绑定的阶段 Agent 发送消息。"""

    model_config = ConfigDict(extra="forbid")

    node_id: UUID
    message: str = Field(default="", max_length=100000)
    message_type: str = Field(default="text", min_length=1, max_length=50)
    payload: dict[str, Any] = Field(default_factory=dict)
    stream: bool = Field(default=True)
    file_ids: list[str] = Field(default_factory=list, max_length=50)
    knowledge_base_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("message", "message_type")
    @classmethod
    def normalize_message_text(cls, value: str) -> str:
        """清理消息文本和消息类型两侧空白。"""
        return (value or "").strip()

    @field_validator("file_ids")
    @classmethod
    def normalize_file_ids(cls, value: list[str]) -> list[str]:
        """清理附件 ID，并按原始顺序去重。"""
        cleaned = [str(item or "").strip() for item in value]
        return list(dict.fromkeys(item for item in cleaned if item))

    @field_validator("knowledge_base_ids")
    @classmethod
    def normalize_knowledge_base_ids(cls, value: list[UUID]) -> list[UUID]:
        """按原始顺序去重知识库 ID。"""
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_message_content(self) -> "NodeAgentMessageRequest":
        """保证文本、结构化负载或附件至少提供一种输入。"""
        if not self.message and not self.payload and not self.file_ids:
            raise ValueError("message、payload 和 file_ids 至少需要提供一项")
        return self


class NodeAgentMessageResponse(BaseModel):
    """非流式节点 Agent 调用响应。"""

    node_id: UUID
    agent_id: str
    conversation_id: str
    run_id: str = ""
    answer: str = ""
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
