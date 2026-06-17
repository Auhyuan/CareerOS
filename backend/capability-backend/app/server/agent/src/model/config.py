import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr


# Agent 服务统一管理模型配置；这里加载 backend/.env，保证 API、脚本和测试读取同一份配置。
load_dotenv(override=True)


def env_bool(name: str, default: bool = False) -> bool:
    """
    读取布尔类型环境变量。

    Args:
        name: 环境变量名称。
        default: 环境变量缺失时使用的默认值。
    """
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class ModelConfig(BaseModel):
    """保存 Agent 服务调用模型时需要的统一连接配置。"""

    provider: str = Field(default="openai_compatible", description="模型供应商类型")
    api_key: SecretStr | None = Field(default=None, description="模型 API Key")
    base_url: str = Field(default="", description="OpenAI 兼容接口地址")
    chat_model: str = Field(default="deepseek-chat", description="默认聊天模型名称")
    embedding_model: str | None = Field(default=None, description="默认 Embedding 模型名称")
    rerank_model: str | None = Field(default=None, description="默认 Rerank 模型名称")
    langsmith_tracing: bool = Field(default=False, description="是否启用 LangSmith 追踪")
    langsmith_api_key: SecretStr | None = Field(default=None, description="LangSmith API Key")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith 地址")
    langsmith_project: str = Field(default="career-ai", description="LangSmith 项目名")

    def get_api_key(self) -> str:
        """
        获取明文模型 API Key。

        Returns:
            可传给 LangChain 模型对象的 API Key 字符串。
        """
        return self.api_key.get_secret_value() if self.api_key else ""

    def get_langsmith_api_key(self) -> str:
        """
        获取明文 LangSmith API Key。

        Returns:
            可写入 LangSmith 环境变量的 API Key 字符串。
        """
        return self.langsmith_api_key.get_secret_value() if self.langsmith_api_key else ""

    def validate_for_runtime(self) -> None:
        """
        校验模型运行前必须具备的配置。

        Raises:
            RuntimeError: 当供应商类型暂不支持，或者模型 API Key 缺失时抛出。
        """
        if self.provider != "openai_compatible":
            raise RuntimeError(f"暂不支持的 MODEL_PROVIDER：{self.provider}")
        if not self.get_api_key():
            raise RuntimeError("MODEL_API_KEY / LLM_API_KEY 未配置，无法调用模型")


@lru_cache(maxsize=1)
def get_model_config() -> ModelConfig:
    """
    从环境变量读取并缓存 Agent 服务的模型配置。

    Returns:
        当前进程内复用的 ModelConfig 配置对象。
    """
    return ModelConfig(
        provider=os.getenv("MODEL_PROVIDER", os.getenv("LLM_PROVIDER", "openai_compatible")).strip(),
        api_key=os.getenv("MODEL_API_KEY") or os.getenv("LLM_API_KEY") or None,
        base_url=os.getenv("MODEL_BASE_URL", os.getenv("LLM_BASE_URL", "")).strip(),
        chat_model=os.getenv("MODEL_CHAT_MODEL", os.getenv("LLM_MODEL", "deepseek-chat")).strip(),
        embedding_model=os.getenv("MODEL_EMBEDDING_MODEL") or None,
        rerank_model=os.getenv("MODEL_RERANK_MODEL") or None,
        langsmith_tracing=env_bool("LANGSMITH_TRACING", False),
        langsmith_api_key=os.getenv("LANGSMITH_API_KEY") or None,
        langsmith_endpoint=os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com").strip(),
        langsmith_project=os.getenv("LANGSMITH_PROJECT", "career-ai").strip(),
    )


def configure_langsmith_environment(config: ModelConfig | None = None) -> None:
    """
    根据配置写入 LangSmith 追踪所需的环境变量。

    Args:
        config: 外部传入的模型配置；不传时读取当前缓存配置。
    """
    current_config = config or get_model_config()
    if not current_config.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = current_config.langsmith_endpoint
    os.environ["LANGCHAIN_ENDPOINT"] = current_config.langsmith_endpoint
    os.environ["LANGSMITH_PROJECT"] = current_config.langsmith_project
    os.environ["LANGCHAIN_PROJECT"] = current_config.langsmith_project

    langsmith_api_key = current_config.get_langsmith_api_key()
    if langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
        os.environ["LANGCHAIN_API_KEY"] = langsmith_api_key
