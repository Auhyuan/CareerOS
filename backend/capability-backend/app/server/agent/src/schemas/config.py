from typing import Any

from pydantic import BaseModel, Field


class AgentFeatureConfig(BaseModel):
    """Agent 内部装配能力开关。

    这个配置只在 agent 服务内部使用，不直接暴露给 API 调用方。
    API 层使用 AgentOptionalFeatures 描述业务能力，AgentService 再把它转换成内部装配配置。
    """

    enable_tool_args_injection: bool = Field(default=True, description="是否启用工具参数自动注入")
    enable_tool_logging: bool = Field(default=True, description="是否启用工具调用日志")
    enable_tool_error_handler: bool = Field(default=True, description="是否启用工具异常处理")
    enable_memory: bool = Field(default=False, description="是否启用记忆相关中间件")
    enable_deferred_tool_filter: bool = Field(default=False, description="是否启用延迟工具筛选")


class AgentBuildConfig(BaseModel):
    """Agent 装配配置。

    这里不包含 agent_id，因为 /agent/run 是通用执行器。
    如果调用方需要基于模板运行，应先通过模板接口拿到配置，再把配置传给 /agent/run。
    """

    system_prompt: str | None = Field(default=None, description="系统提示词")
    response_format: dict[str, Any] | None = Field(
        default=None,
        description="传给 LangChain create_agent 的结构化输出 JSON Schema",
    )
    tool_names: list[str] = Field(default_factory=list, description="允许加载的工具名称")
    features: AgentFeatureConfig = Field(default_factory=AgentFeatureConfig, description="Agent 内部装配能力开关")
