from typing import Any

from pydantic import BaseModel, Field, field_validator


class ModelRuntimeOptions(BaseModel):
    """单次模型调用的运行参数。"""

    model: str | None = Field(default=None, description="model_gateway.yaml 中的模型别名；为空时使用 chat_main")
    temperature: float = Field(default=0.2, ge=0, le=2, description="模型采样温度")
    timeout_seconds: int | None = Field(default=None, ge=1, description="模型调用超时时间；为空时使用模型网关配置")
    max_retries: int = Field(default=2, ge=0, description="模型调用最大重试次数")


class AgentOptionalFeatures(BaseModel):
    """本次 Agent 运行可选择开启的增强能力。"""

    long_term_memory_enabled: bool = Field(default=False, description="是否启用长期记忆能力")
    conversation_context_enabled: bool = Field(default=False, description="是否启用会话上下文增强")
    deferred_tool_filter_enabled: bool = Field(default=False, description="是否启用延迟工具筛选能力")


class AgentRunRequest(BaseModel):
    """通用 Agent 真实运行请求模型。

    /agent/run 是通用执行器，只接收本次运行真正需要的参数。
    它不绑定 agent_id，不包含 dry_run，也不承担调用追踪字段。
    """

    query: str = Field(..., min_length=1, description="用户输入或编排层传入的任务指令")
    conversation_id: str | None = Field(default=None, description="会话 ID 或任务线程 ID")
    system_prompt: str | None = Field(default=None, description="本次运行使用的系统提示词")
    response_format: dict[str, Any] | None = Field(
        default=None,
        description="结构化输出 JSON Schema；为空时不启用结构化输出",
    )
    inputs: dict[str, Any] = Field(default_factory=dict, description="编排层注入的业务变量")
    files: list[dict[str, Any]] = Field(default_factory=list, description="附件上下文")
    tools: list[str] = Field(default_factory=list, description="本次运行允许使用的工具名称")
    optional_features: AgentOptionalFeatures = Field(default_factory=AgentOptionalFeatures, description="本次运行可选择开启的增强能力")
    runtime_options: ModelRuntimeOptions = Field(default_factory=ModelRuntimeOptions, description="模型运行参数")

    @field_validator("response_format")
    @classmethod
    def normalize_response_format(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        规范化结构化输出配置，空对象与 null 都表示不启用结构化输出。

        Args:
            value: 调用方传入的 JSON Schema。

        Returns:
            非空 JSON Schema；未配置或传入空对象时返回 None。
        """
        return value or None
