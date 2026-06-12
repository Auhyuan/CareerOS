from typing import Any

from app.server.agent.src.tools.registry import AgentToolRegistry


class AgentToolService:
    """Agent 工具服务。"""

    def __init__(self, registry: AgentToolRegistry | None = None):
        """
        初始化 Agent 工具服务。

        Args:
            registry: 工具注册中心；不传时创建默认注册中心。
        """
        self.registry = registry or AgentToolRegistry()

    def list_tools(self) -> list[str]:
        """
        查询当前注册的工具名称。

        Returns:
            工具名称列表。
        """
        return self.registry.list_tools()

    def get_tools(self, tool_names: list[str] | None = None) -> list[Any]:
        """
        根据名称获取工具对象。

        Args:
            tool_names: 需要加载的工具名称；为空时返回全部工具。

        Returns:
            可传给 LangChain Agent 的工具对象列表。
        """
        if not tool_names:
            return self.registry.get_all_tools()
        return [self.registry.get_tool(name) for name in tool_names if self.registry.has_tool(name)]
