from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AIBackendConfig(BaseSettings):
    """AI-backend 服务调用配置。"""

    # 允许通过 orchestration-backend 的 .env 覆盖 AI-backend 地址与超时时间。
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ai_backend_base_url: str = Field(default="http://127.0.0.1:8090", description="AI-backend 服务地址")
    ai_backend_timeout_seconds: int = Field(default=180, ge=1, description="调用 AI-backend 的超时时间")


def get_ai_backend_config() -> AIBackendConfig:
    """获取 AI-backend 服务调用配置。

    Returns:
        AI-backend 服务调用配置对象。
    """
    return AIBackendConfig()
