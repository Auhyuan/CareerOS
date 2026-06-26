from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.server.agent.src.schemas.request import AgentA2AConfig, AgentOptionalFeatures, ModelRuntimeOptions


class AgentTemplateConfig(BaseModel):
    """Agent 模板运行配置，对应通用 Agent 的可复用装配参数。"""

    # 模板配置保存在 JSONB 中，允许额外字段可避免后续扩展 Agent 参数时立即修改表结构。
    model_config = ConfigDict(extra="allow")

    system_prompt: str | None = Field(default=None, description="Agent 默认系统提示词")
    response_format: dict[str, Any] | None = Field(
        default=None,
        description="结构化输出 JSON Schema；为空时不启用结构化输出",
    )
    tools: list[str] = Field(default_factory=list, description="Agent 默认可用工具名称")
    optional_features: AgentOptionalFeatures = Field(
        default_factory=AgentOptionalFeatures,
        description="Agent 默认可选能力配置",
    )
    is_sub_agent: bool = Field(default=False, description="是否可被其他 Agent 通过 A2A 调用")
    a2a: AgentA2AConfig | None = Field(
        default=None,
        description="模板默认 A2A 配置；sub_agent_list 非空时，运行时可动态装配 a2a_call 工具。",
    )
    runtime_options: ModelRuntimeOptions = Field(
        default_factory=ModelRuntimeOptions,
        description="Agent 默认模型运行参数",
    )

    @field_validator("response_format")
    @classmethod
    def normalize_response_format(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        规范化模板中的结构化输出配置。

        Args:
            value: 模板保存的 JSON Schema。

        Returns:
            非空 JSON Schema；未配置或传入空对象时返回 None。
        """
        return value or None


class AgentTemplateUpsertRequest(BaseModel):
    """创建或更新 Agent 模板的请求参数。"""

    agent_id: str = Field(..., min_length=1, max_length=100, description="Agent 稳定业务 ID")
    agent_name: str = Field(..., min_length=1, max_length=255, description="Agent 展示名称")
    description: str | None = Field(default=None, description="Agent 模板描述")
    config: AgentTemplateConfig = Field(default_factory=AgentTemplateConfig, description="Agent 模板配置")
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
    config: AgentTemplateConfig = Field(default_factory=AgentTemplateConfig, description="Agent 模板配置")
    status: str = Field(default="active", description="模板状态")
    created_at: str | None = Field(default=None, description="创建时间")
    updated_at: str | None = Field(default=None, description="更新时间")


class AgentTemplateSearchResponse(BaseModel):
    """Agent 模板分页查询响应。"""

    total: int = Field(default=0, description="总数量")
    page: int = Field(default=1, description="页码")
    page_size: int = Field(default=20, description="每页数量")
    items: list[AgentTemplateView] = Field(default_factory=list, description="模板列表")


class AgentTemplateDeleteRequest(BaseModel):
    """批量删除 Agent 模板的请求参数。"""

    agent_ids: list[str] = Field(
        ...,
        min_length=1,
        description="待删除的 Agent 稳定业务 ID 列表，至少包含一个",
    )
