from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class JobToolConfig(BaseSettings):
    """Job 业务工具调用 orchestration-backend 的连接配置。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    orchestration_base_url: str = Field(
        default="http://127.0.0.1:8091",
        description="业务编排层服务基础地址",
    )
    orchestration_timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Job 工具调用业务编排层的超时时间",
    )


def get_job_tool_config() -> JobToolConfig:
    """
    获取 Job 工具调用配置。

    Returns:
        Job 工具连接配置。
    """
    return JobToolConfig()
