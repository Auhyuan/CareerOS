from typing import Any

from pydantic import BaseModel, Field, field_validator


class ModelRuntimeOptions(BaseModel):
    """单次模型调用的运行参数。

    该模型只描述“怎么调用模型”，不负责控制会话记忆、checkpointer 或 A2A 行为。
    会话状态是否持久化统一由 AgentRunRequest.conversation_id 控制。
    """

    model: str | None = Field(
        default=None,
        description="model_gateway.yaml 中的模型别名；为空时使用默认聊天模型 chat_main。",
    )
    temperature: float = Field(
        default=0.2,
        ge=0,
        le=2,
        description="模型采样温度，数值越低输出越稳定，数值越高输出越发散。",
    )
    timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        description="模型调用超时时间；为空时使用模型网关配置。",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description="模型调用失败时的最大重试次数。",
    )


class AgentOptionalFeatures(BaseModel):
    """本次 Agent 运行可以显式开启的增强能力。

    基础能力，例如工具调用日志、工具错误处理、检索上下文注入，已经由中间件默认装配，
    不再通过请求参数控制。
    """

    long_term_memory_enabled: bool = Field(
        default=False,
        description="是否启用长期记忆能力；当前为预留能力，不等同于 conversation_id 控制的会话上下文。",
    )


class AgentA2AConfig(BaseModel):
    """A2A 调用配置。

    只要 sub_agent_list 非空，本次 Agent 运行就会动态装配 a2a_call 工具，
    并通过 A2A 中间件把可调用子 Agent 信息注入系统提示词。
    """

    sub_agent_list: list[str] = Field(
        default_factory=list,
        description="本次允许调用的子 Agent ID 列表；为空或不传时不启用 A2A。",
    )


class AgentRunRequest(BaseModel):
    """通用 Agent 真实运行请求模型。

    /agent/run 是通用执行器，不绑定 agent_id。调用方如果想基于某个模板运行，
    应先通过模板接口获取配置，再把 system_prompt、response_format、tools、a2a、runtime_options 等配置传入本请求。

    conversation_id 是会话记忆的唯一开关：
    - conversation_id 非空：作为 LangGraph thread_id，启用 PostgreSQL checkpointer，并写入用户可见会话记录。
    - conversation_id 为空：视为一次性任务或 A2A 子 Agent 调用，不启用 checkpointer，不写入 agent_conversations / agent_messages。
    """

    query: str = Field(
        ...,
        min_length=1,
        description="用户输入或编排层传入的任务指令。",
    )
    conversation_id: str | None = Field(
        default=None,
        description="会话 ID；非空时启用 checkpointer 和会话记录，空值时按一次性无会话任务运行。",
    )
    stream: bool = Field(
        default=False,
        description="是否使用 SSE 流式返回；true 时 /agent/run 返回 text/event-stream。",
    )
    system_prompt: str | None = Field(
        default=None,
        description="本次运行使用的系统提示词；通常来自 Agent 模板配置。",
    )
    response_format: dict[str, Any] | None = Field(
        default=None,
        description="结构化输出 JSON Schema；为空时不启用结构化输出。",
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="编排层注入的业务变量，可用于 prompt 渲染和 runtime context。",
    )
    files: list[dict[str, Any]] = Field(
        default_factory=list,
        description="附件上下文预留字段；当前先作为 runtime context 透传。",
    )
    tools: list[str] = Field(
        default_factory=list,
        description="本次运行允许加载的常规工具名称；A2A 工具不需要写入这里，由 a2a.sub_agent_list 动态控制。",
    )
    optional_features: AgentOptionalFeatures = Field(
        default_factory=AgentOptionalFeatures,
        description="本次运行可选增强能力；不包含默认始终开启的基础中间件能力。",
    )
    a2a: AgentA2AConfig | None = Field(
        default=None,
        description="A2A 调用配置；sub_agent_list 非空时启用 A2A 动态工具和上下文注入。",
    )
    runtime_options: ModelRuntimeOptions = Field(
        default_factory=ModelRuntimeOptions,
        description="模型运行参数，只控制模型别名、温度、超时和重试次数。",
    )

    @field_validator("response_format")
    @classmethod
    def normalize_response_format(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """规范化结构化输出配置。

        Args:
            value: 调用方传入的 JSON Schema。

        Returns:
            非空 JSON Schema；未配置或传入空对象时返回 None。
        """
        return value or None