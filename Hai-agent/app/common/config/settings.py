from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """集中管理 Hai-agent 的服务、数据库和 JWT 配置。"""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Hai-agent")
    app_host: str = Field(default="127.0.0.1")
    app_port: int = Field(default=8093, ge=1, le=65535)
    app_reload: bool = Field(default=True)

    ai_backend_base_url: str = Field(default="http://127.0.0.1:8090")
    ai_backend_connect_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    ai_backend_timeout_seconds: float = Field(default=900.0, gt=0, le=3600)

    postgres_host: str = Field(default="127.0.0.1")
    postgres_port: int = Field(default=5433, ge=1, le=65535)
    postgres_user: str = Field(default="remote_root")
    postgres_password: str = Field(default="")
    postgres_database: str = Field(default="career_ai")
    postgres_schema: str = Field(default="hai_agent")
    postgres_connect_timeout: int = Field(default=5, ge=1, le=60)
    postgres_pool_size: int = Field(default=10, ge=1, le=100)
    postgres_max_overflow: int = Field(default=20, ge=0, le=200)

    jwt_secret_key: str = Field(default="change-this-secret-before-startup")
    jwt_algorithm: str = Field(default="HS256")
    jwt_issuer: str = Field(default="hai-agent")
    jwt_audience: str = Field(default="hai-agent-web")
    jwt_access_token_minutes: int = Field(default=30, ge=1, le=1440)
    jwt_refresh_token_days: int = Field(default=14, ge=1, le=90)

    project_preparation_agent_id: str | None = Field(default=None)
    requirement_confirmation_agent_id: str | None = Field(default=None)
    creative_direction_agent_id: str | None = Field(default=None)
    proposal_generation_agent_id: str | None = Field(default=None)
    feedback_revision_agent_id: str | None = Field(default=None)

    mcp_service_name: str = Field(default="hai-agent-workflow-tools")
    mcp_mount_path: str = Field(default="/mcp")
    mcp_transport_path: str = Field(default="/")

    cors_origins: str = Field(default="http://127.0.0.1:5173,http://localhost:5173")

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的跨域来源转换为列表。"""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回进程内复用的配置对象。"""
    return Settings()
