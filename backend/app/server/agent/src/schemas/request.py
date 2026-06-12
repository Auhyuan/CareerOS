from typing import Any

from pydantic import BaseModel, Field


class ModelRuntimeOptions(BaseModel):
    """单次模型调用的运行参数。"""

    model: str | None = Field(default=None, description="本次调用使用的模型名称")
    temperature: float = Field(default=0.2, ge=0, le=2, description="模型采样温度")
    timeout_seconds: int = Field(default=60, ge=1, description="模型调用超时时间")
    max_retries: int = Field(default=2, ge=0, description="模型调用最大重试次数")


class AgentOptionalFeatures(BaseModel):
    """本次 Agent 运行可选择开启的增强能力。

    注意：这里描述的是“业务能力”，不是“中间件名称”。
    调用方只需要关心要不要启用长期记忆、checkpoint 等能力；
    至于这些能力底层由哪些中间件实现，由 agent 服务内部决定。
    """

    long_term_memory_enabled: bool = Field(default=False, description="是否启用长期记忆能力")
    short_term_context_enabled: bool = Field(default=False, description="是否启用短期会话上下文增强")
    checkpoint_enabled: bool = Field(default=False, description="是否启用 LangGraph checkpoint 状态持久化")
    deferred_tool_filter_enabled: bool = Field(default=False, description="是否启用延迟工具过滤能力")


class AgentRunRequest(BaseModel):
    """通用 Agent 运行请求模型。"""

    agent_name: str = Field(default="default", description="Agent 名称")
    query: str = Field(..., min_length=1, description="用户输入或编排层传入的任务指令")
    conversation_id: str | None = Field(default=None, description="会话 ID 或任务线程 ID")
    user_id: str | None = Field(default=None, description="调用方用户 ID")
    request_id: str | None = Field(default=None, description="调用方请求 ID")
    system_prompt: str | None = Field(default=None, description="本次运行使用的系统提示词")
    inputs: dict[str, Any] = Field(default_factory=dict, description="编排层注入的业务变量")
    files: list[dict[str, Any]] = Field(default_factory=list, description="附件上下文")
    input_messages: list[dict[str, Any]] = Field(default_factory=list, description="历史输入消息")
    tools: list[str] = Field(default_factory=list, description="本次运行允许使用的工具名称")
    optional_features: AgentOptionalFeatures = Field(default_factory=AgentOptionalFeatures, description="本次运行可选择开启的增强能力")
    dry_run: bool = Field(default=True, description="是否只返回装配信息，不真实调用模型")
    runtime_options: ModelRuntimeOptions = Field(default_factory=ModelRuntimeOptions, description="模型运行参数")
