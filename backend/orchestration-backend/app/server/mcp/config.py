from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPConfig(BaseSettings):
    """业务编排层 MCP 服务配置。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mcp_service_name: str = Field(default="career-ai-orchestration-tools", description="MCP 服务名称")
    mcp_mount_path: str = Field(default="/mcp", description="MCP ASGI 应用挂载到 FastAPI 的路径")
    mcp_transport_path: str = Field(default="/", description="FastMCP 在挂载路径内部使用的传输路径")
    mcp_host: str = Field(default="127.0.0.1", description="MCP 独立服务启动地址")
    mcp_port: int = Field(default=8092, ge=1, le=65535, description="MCP 独立服务启动端口")


def get_mcp_config() -> MCPConfig:
    """从环境变量中读取 MCP 服务配置。

    Returns:
        MCP 服务配置对象。
    """
    return MCPConfig()
