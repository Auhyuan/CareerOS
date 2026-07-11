import logging
from typing import Any

from app.server.mcp.config import MCPConfig, get_mcp_config
from app.server.mcp.job_profile_tools import register_job_profile_tools
from app.server.mcp.job_skill_tools import register_job_skill_tools

logger = logging.getLogger(__name__)


def create_mcp_server(config: MCPConfig | None = None) -> Any | None:
    """创建并配置 FastMCP 服务实例。

    Args:
        config: 可选的 MCP 服务配置。

    Returns:
        FastMCP 服务实例；如果当前环境没有安装 FastMCP，则返回 None。
    """
    runtime_config = config or get_mcp_config()
    try:
        from fastmcp import FastMCP
    except ImportError:
        logger.warning("FastMCP 未安装，业务编排层 MCP 服务已跳过挂载。")
        return None

    mcp = FastMCP(runtime_config.mcp_service_name)
    register_job_skill_tools(mcp)
    register_job_profile_tools(mcp)
    logger.info("MCP 工具注册完成: names=['search_job_skills', 'create_job_skills', 'save_job_profile']")
    return mcp


def create_mcp_asgi_app(config: MCPConfig | None = None) -> Any | None:
    """创建可挂载到业务编排层 FastAPI 的 MCP ASGI 应用。

    Args:
        config: 可选的 MCP 服务配置。

    Returns:
        FastMCP 返回的 ASGI 应用；如果 FastMCP 不可用或当前版本不支持 ASGI 挂载，则返回 None。
    """
    runtime_config = config or get_mcp_config()
    mcp = create_mcp_server(runtime_config)
    if mcp is None:
        return None

    if not hasattr(mcp, "http_app"):
        logger.warning("当前 FastMCP 版本没有 http_app()，MCP 挂载已跳过。")
        return None

    # 不同 FastMCP 版本的 http_app 参数略有差异，这里做兼容处理，避免影响业务编排层主服务启动。
    try:
        return mcp.http_app(path=runtime_config.mcp_transport_path)
    except TypeError:
        return mcp.http_app()


def run_mcp_server() -> None:
    """以独立 HTTP 服务方式启动业务编排层 MCP 服务。

    当前阶段默认把 MCP 挂载到 orchestration-backend 中；这个入口预留给后续独立部署使用。
    """
    config = get_mcp_config()
    mcp = create_mcp_server(config)
    if mcp is None:
        raise RuntimeError("FastMCP 未安装，请先安装 orchestration-backend 的依赖。")

    mcp.run(transport="http", host=config.mcp_host, port=config.mcp_port, path=config.mcp_transport_path)
