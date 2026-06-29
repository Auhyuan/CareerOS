from typing import Any

from pydantic import BaseModel, Field, field_validator


class ModelRuntimeOptions(BaseModel):
    """单次模型调用的运行参数。

    这里只描述“怎么调用模型”。模型连接信息通过 model_code 从 model 表模块中的 model_configs 表读取；
    temperature、timeout_seconds、max_retries 属于具体 Agent/任务场景，因此保留在运行参数里。
    """

    model_code: str | None = Field(
        default=None,
        description="平台模型编码，必须指向 model_configs 中已启用的 chat 模型。",
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
        description="模型调用超时时间；为空时交给模型客户端使用默认值。",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description="模型调用失败时的最大重试次数。",
    )

    @field_validator("model_code")
    @classmethod
    def normalize_model_code(cls, value: str | None) -> str | None:
        """清理模型编码两侧空白，空字符串视为未配置。"""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


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
    应先通过模板接口获取配置，再把 system_prompt、、tools、a2a、runtime_options 等配置传入本请求。

    conversation_id 是会话记忆的唯一开关：
    - conversation_id 非空：作为 LangGraph thread_id，启用 PostgreSQL checkpointer，并写入用户可见会话记录。
    - conversation_id 为空：视为一次性任务或 A2A 子 Agent 调用，不启用 checkpointer，不写入 agent_conversations / agent_messages。
    """

    query: str = Field(..., min_length=1, description="用户输入或编排层传入的任务指令。")
    conversation_id: str | None = Field(
        default=None,
        description="会话 ID；非空时启用 checkpointer 和会话记录，空值时按一次性无会话任务运行。",
    )
    stream: bool = Field(default=False, description="是否使用 SSE 流式返回。")
    system_prompt: str | None = Field(default=None, description="本次运行使用的系统提示词。")
    inputs: dict[str, Any] = Field(default_factory=dict, description="编排层注入的业务变量。")
    files: list[dict[str, Any]] = Field(default_factory=list, description="附件上下文预留字段。")
    tools: list[str] = Field(
        default_factory=list,
        description="本次运行允许加载的常规工具名称；A2A 工具由 a2a.sub_agent_list 动态控制。",
    )
    optional_features: AgentOptionalFeatures = Field(
        default_factory=AgentOptionalFeatures,
        description="本次运行可选增强能力。",
    )
    a2a: AgentA2AConfig | None = Field(default=None, description="A2A 调用配置。")
    runtime_options: ModelRuntimeOptions = Field(
        default_factory=ModelRuntimeOptions,
        description="模型运行参数，必须包含可用 chat 模型的 model_code。",
    )

