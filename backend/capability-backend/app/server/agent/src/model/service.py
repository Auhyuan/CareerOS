import logging
from typing import Any

from app.server.agent.src.model.config import ModelConfig, configure_langsmith_environment, get_model_config


logger = logging.getLogger("capability.agent.model")


class AgentModelService:
    """Agent 服务的模型调用入口。"""

    def __init__(self, config: ModelConfig | None = None):
        """
        初始化 Agent 模型服务。

        Args:
            config: 外部传入的模型网关配置；不传时读取 Agent 根目录 model_gateway.yaml。
        """
        self.config = config or get_model_config()
        logger.info(
            "Model gateway loaded: path=%s default_chat=%s available_aliases=%s",
            self.config.gateway_path,
            self.config.default_chat_alias,
            sorted(self.config.models),
        )

    def create_chat_model(
        self,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        timeout_seconds: int | None = None,
        max_retries: int = 2,
    ) -> Any:
        """
        根据模型别名创建 LangChain ChatModel 实例。

        Args:
            model: model_gateway.yaml 中的 LLM 模型别名；不传时使用 chat_main。
            temperature: 本次模型调用的采样温度。
            timeout_seconds: 本次调用超时时间；不传时使用 YAML 中的 timeout。
            max_retries: 本次模型调用的最大重试次数。

        Returns:
            LangChain 可直接 invoke 的聊天模型对象。
        """
        configure_langsmith_environment(self.config)
        definition = self.config.resolve_model(model, expected_kind="llm")
        selected_alias = model or self.config.default_chat_alias
        effective_timeout = timeout_seconds or definition.timeout
        logger.info(
            "Chat model initializing: alias=%s provider=%s model=%s base_url=%s temperature=%s timeout=%s max_retries=%s",
            selected_alias,
            definition.provider,
            definition.model,
            definition.base_url,
            temperature,
            effective_timeout,
            max_retries,
        )

        from langchain_openai import ChatOpenAI

        chat_model = ChatOpenAI(
            api_key=definition.get_api_key(),
            base_url=definition.base_url or None,
            model=definition.model,
            temperature=temperature,
            timeout=effective_timeout,
            max_retries=max_retries,
        )
        logger.info("Chat model initialized: alias=%s model=%s", selected_alias, definition.model)
        return chat_model

    def create_embedding_model(self, model: str | None = None) -> Any:
        """
        根据模型别名创建 Embedding 模型实例。

        Args:
            model: model_gateway.yaml 中的 Embedding 模型别名；不传时使用 embed_search。

        Returns:
            LangChain Embedding 模型对象。
        """
        definition = self.config.resolve_model(model, expected_kind="embedding")
        selected_alias = model or self.config.default_embedding_alias
        logger.info(
            "Embedding model initializing: alias=%s provider=%s model=%s base_url=%s timeout=%s dimension=%s",
            selected_alias,
            definition.provider,
            definition.model,
            definition.base_url,
            definition.timeout,
            definition.dimension,
        )

        from langchain_openai import OpenAIEmbeddings

        embedding_model = OpenAIEmbeddings(
            api_key=definition.get_api_key(),
            base_url=definition.base_url or None,
            model=definition.model,
            request_timeout=definition.timeout,
            check_embedding_ctx_length=False,
        )
        logger.info("Embedding model initialized: alias=%s model=%s", selected_alias, definition.model)
        return embedding_model


def create_chat_model(
    *,
    model: str | None = None,
    temperature: float = 0.2,
    timeout_seconds: int | None = None,
    max_retries: int = 2,
) -> Any:
    """
    创建默认 Agent 聊天模型。

    Args:
        model: model_gateway.yaml 中的模型别名。
        temperature: 本次模型调用的采样温度。
        timeout_seconds: 本次调用超时时间；不传时使用 YAML 配置。
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
