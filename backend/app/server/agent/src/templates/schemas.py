from typing import Any

from pydantic import BaseModel, Field


class AgentTemplateUpsertRequest(BaseModel):
    """创建或更新 Agent 模板的请求参数。"""

    agent_id: str = Field(..., min_length=1, max_length=100, description="Agent 稳定业务 ID")
    agent_name: str = Field(..., min_length=1, max_length=255, description="Agent 展示名称")
    description: str | None = Field(default=None, description="Agent 模板描述")
    config: dict[str, Any] = Field(default_factory=dict, description="Agent 模板配置，使用 JSONB 灵活存储")
    status: str = Field(default="active", max_length=30, description="模板状态，例如 active、disabled")


class AgentTemplateDetailRequest(BaseModel):
    """查询 Agent 模板详情的请求参数。"""

    agent_id: str = Field(..., min_length=1, max_length=100, description="Agent 稳定业务 ID")


class AgentTemplateSearchRequest(BaseModel):
    """查询 Agent 模板列表的请求参数。"""

    keyword: str | None = Field(default=None, description="关键字，匹配 agent_id、agent_name、description")
    status: str | None = Field(default=None, max_length=30, description="模板状态")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class AgentTemplateView(BaseModel):
    """返回给接口调用方的 Agent 模板视图。"""

    agent_id: str = Field(..., description="Agent 稳定业务 ID")
    agent_name: str = Field(..., description="Agent 展示名称")
    description: str | None = Field(default=None, description="Agent 模板描述")
    config: dict[str, Any] = Field(default_factory=dict, description="Agent 模板配置")
    status: str = Field(default="active", description="模板状态")
    created_at: str | None = Field(default=None, description="创建时间")
    updated_at: str | None = Field(default=None, description="更新时间")


class AgentTemplateSearchResponse(BaseModel):
    """Agent 模板分页查询响应。"""

    total: int = Field(default=0, description="总数量")
    page: int = Field(default=1, description="页码")
    page_size: int = Field(default=20, description="每页数量")
    items: list[AgentTemplateView] = Field(default_factory=list, description="模板列表")
