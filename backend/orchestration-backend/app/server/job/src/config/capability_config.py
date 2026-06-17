from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CapabilityBackendConfig(BaseSettings):
    """能力层服务调用配置。"""

    # 编排层通过环境变量读取能力层地址，避免把服务地址写死在业务代码里。
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    capability_base_url: str = Field(default="http://127.0.0.1:8090", description="能力层服务基础地址")
    capability_timeout_seconds: int = Field(default=180, ge=1, description="调用能力层接口的超时时间")


def get_capability_backend_config() -> CapabilityBackendConfig:
    """
    获取能力层服务调用配置。

    Returns:
        能力层服务调用配置对象。
    """
    return CapabilityBackendConfig()
