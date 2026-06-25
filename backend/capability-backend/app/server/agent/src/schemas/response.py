from typing import Any

from pydantic import BaseModel, Field


class ModelConfigResponse(BaseModel):
    """脱敏后的模型配置响应。"""

    gateway_path: str = Field(..., description="模型网关 YAML 文件路径")
    available_models: list[str] = Field(default_factory=list, description="可用模型别名")
    provider: str = Field(..., description="模型供应商类型")
    base_url: str = Field(..., description="OpenAI 兼容接口地址")
    chat_model: str = Field(..., description="默认聊天模型名称")
    embedding_model: str | None = Field(default=None, description="默认 Embedding 模型名称")
    rerank_model: str | None = Field(default=None, description="默认 Rerank 模型名称")
    langsmith_tracing: bool = Field(..., description="是否启用 LangSmith 追踪")
    langsmith_endpoint: str = Field(..., description="LangSmith 地址")
    langsmith_project: str = Field(..., description="LangSmith 项目名")
    has_api_key: bool = Field(..., description="是否已经配置模型 API Key")
    has_langsmith_api_key: bool = Field(..., description="是否已经配置 LangSmith API Key")


class AgentCapabilityResponse(BaseModel):
    """Agent 服务能力响应。"""

    service_name: str = Field(..., description="服务名称")
    modules: list[str] = Field(default_factory=list, description="Agent 服务内部模块")
    enabled_features: list[str] = Field(default_factory=list, description="当前已规划或可用的能力")
    registered_tools: list[str] = Field(default_factory=list, description="当前已注册的 Agent 工具名称")


class AgentRunResponse(BaseModel):
    """通用 Agent 运行响应模型。"""

    run_id: str = Field(default="", description="Agent 本次运行 ID")
    answer: str = Field(default="", description="Agent 输出文本")
    structured_output: dict[str, Any] | None = Field(default=None, description="结构化输出结果")
