from typing import Any

from app.server.agent.src.model.config import ModelConfig, configure_langsmith_environment, get_model_config


class AgentModelService:
    """Agent 服务的模型调用入口。"""

    def __init__(self, config: ModelConfig | None = None):
        """
        初始化 Agent 模型服务。

        Args:
            config: 外部传入的模型配置；不传时从 backend/.env 读取默认配置。
        """
        self.config = config or get_model_config()

    def create_chat_model(
        self,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        timeout_seconds: int = 60,
        max_retries: int = 2,
    ) -> Any:
        """
        创建 LangChain ChatModel 实例。

        Args:
            model: 本次调用使用的聊天模型名称；不传时使用环境变量中的默认聊天模型。
            temperature: 本次模型调用的采样温度。
            timeout_seconds: 本次模型调用的超时时间。
            max_retries: 本次模型调用的最大重试次数。

        Returns:
            LangChain 可直接 invoke / with_structured_output 的聊天模型对象。
        """
        self.config.validate_for_runtime()
        configure_langsmith_environment(self.config)

        try:
            from langchain_openai import ChatOpenAI
        except ImportError as error:
            raise RuntimeError("缺少 langchain-openai 依赖，请先执行：pip install -r requirements.txt") from error

        return ChatOpenAI(
            api_key=self.config.get_api_key(),
            base_url=self.config.base_url or None,
            model=model or self.config.chat_model,
            temperature=temperature,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    def create_embedding_model(self) -> Any:
        """
        创建 Embedding 模型实例。

        Returns:
            LangChain Embedding 模型对象。
        """
        self.config.validate_for_runtime()
        if not self.config.embedding_model:
            raise RuntimeError("MODEL_EMBEDDING_MODEL 未配置，无法创建 Embedding 模型")

        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as error:
            raise RuntimeError("缺少 langchain-openai 依赖，请先执行：pip install -r requirements.txt") from error

        return OpenAIEmbeddings(
            api_key=self.config.get_api_key(),
            base_url=self.config.base_url or None,
            model=self.config.embedding_model,
            check_embedding_ctx_length=False,
        )


def create_chat_model(
    *,
    model: str | None = None,
    temperature: float = 0.2,
    timeout_seconds: int = 60,
    max_retries: int = 2,
) -> Any:
    """
    创建默认 Agent 聊天模型。

    Args:
        model: 本次调用使用的模型名称；不传时使用环境变量中的默认模型。
        temperature: 本次模型调用的采样温度。
        timeout_seconds: 本次模型调用的超时时间。
        max_retries: 本次模型调用的最大重试次数。

    Returns:
        LangChain 聊天模型对象。
    """
    return AgentModelService().create_chat_model(
        model=model,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
