"""创建并挂载 Hai-agent FastMCP 服务。"""

import logging
from typing import Any

from fastmcp import FastMCP

from app.common.config.settings import get_settings
from app.server.mcp.workflow_tools import register_workflow_tools


logger = logging.getLogger("hai_agent.mcp")


def create_mcp_server() -> FastMCP:
    """创建 MCP 服务并注册全部 Hai-agent 业务工具。"""
    settings = get_settings()
    mcp = FastMCP(settings.mcp_service_name)
    register_workflow_tools(mcp)
    logger.info("Hai-agent MCP 工具注册完成: names=['save_stage_result']")
    return mcp


def create_mcp_asgi_app() -> Any:
    """创建挂载到 Hai-agent FastAPI 的 MCP ASGI 子应用。"""
    settings = get_settings()
    mcp = create_mcp_server()
    return mcp.http_app(path=settings.mcp_transport_path)
