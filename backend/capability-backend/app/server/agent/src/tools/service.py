import logging
from typing import Any

from app.server.agent.src.tools.base import AgentToolDefinition
from app.server.agent.src.tools.job_tools import create_job_tools
from app.server.agent.src.tools.registry import AgentToolRegistry


logger = logging.getLogger("capability.agent.tools")


class AgentToolService:
    """Agent 工具服务，负责内置工具注册和本次运行工具筛选。"""

    def __init__(self, registry: AgentToolRegistry | None = None):
        """
        初始化 Agent 工具服务。

        Args:
            registry: 工具注册中心；不传时创建并注册平台内置工具。
        """
        self.registry = registry or AgentToolRegistry()
        if registry is None:
            self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """
        注册 Agent 平台当前提供的内置工具。

        Job 工具只负责调用 orchestration-backend API，不直接访问 Job 数据库。
        """
        for tool in create_job_tools():
            self.registry.register(
                AgentToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    callable_ref=tool,
                )
            )
        logger.info("Agent built-in tools registered: names=%s", self.registry.list_tools())

    def list_tools(self) -> list[str]:
        """
        查询当前注册的工具名称。

        Returns:
            工具名称列表。
        """
        return self.registry.list_tools()

    def get_tools(self, tool_names: list[str] | None = None) -> list[Any]:
        """
        根据名称获取本次 Agent 允许使用的工具对象。

        Args:
            tool_names: 工具名称白名单；None 返回全部工具，空列表表示不加载工具。

        Returns:
            可传给 LangChain Agent 的工具对象列表。

        Raises:
            RuntimeError: 请求中包含尚未注册的工具名称。
        """
        if tool_names is None:
            return self.registry.get_all_tools()
        if not tool_names:
            return []

        missing_names = [name for name in tool_names if not self.registry.has_tool(name)]
        if missing_names:
            raise RuntimeError(f"Agent 请求了未注册的工具: {', '.join(missing_names)}")
        return [self.registry.get_tool(name) for name in tool_names]
