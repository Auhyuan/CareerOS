from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreateRequest(BaseModel):
    """创建活动策划项目的参数。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    customer_name: str | None = Field(default=None, max_length=255)
    brand_name: str | None = Field(default=None, max_length=255)
    event_type: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    metadata: dict = Field(default_factory=dict)


class ProjectSearchRequest(BaseModel):
    """查询当前用户项目列表的参数。"""

    keyword: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=30)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ProjectDetailRequest(BaseModel):
    """查询单个项目详情的参数。"""

    project_id: UUID


class ProjectResponse(BaseModel):
    """项目基础响应。"""

    project_id: UUID
    name: str
    customer_name: str | None
    brand_name: str | None
    event_type: str | None
    description: str | None
    status: str
    current_stage: str
    current_branch_id: UUID | None
    current_node_id: UUID | None
    metadata: dict
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """分页项目列表响应。"""

    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int


class BranchResponse(BaseModel):
    """工作流分支响应。"""

    branch_id: UUID
    name: str
    source_branch_id: UUID | None
    source_node_id: UUID | None
    head_node_id: UUID | None
    status: str
    is_main: bool
    created_at: datetime


class NodeResponse(BaseModel):
    """工作流节点响应。"""

    node_id: UUID
    branch_id: UUID
    parent_node_id: UUID | None
    sequence_no: int
    stage_code: str
    status: str
    title: str
    summary: str | None
    input_context: dict
    result_data: dict
    handoff_context: dict
    result_version: int
    agent_id: str | None
    agent_thread_id: str | None
    created_at: datetime
    completed_at: datetime | None


class ProjectDetailResponse(BaseModel):
    """项目、分支和节点组成的项目详情。"""

    project: ProjectResponse
    branches: list[BranchResponse]
    nodes: list[NodeResponse]
