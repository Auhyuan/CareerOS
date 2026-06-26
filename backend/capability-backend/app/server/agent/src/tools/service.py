import inspect
import logging
from typing import Any

from app.common.core.exceptions import BusinessException
from app.server.agent.src.tools.a2a_tool import a2a_call
from app.server.agent.src.tools.base import AgentToolDefinition
from app.server.agent.src.tools.job_tools import JOB_TOOLS
from app.server.agent.src.tools.registry import AgentToolRegistry
from app.server.agent.src.tools.schemas import AgentToolInfo


logger = logging.getLogger("capability.agent.tools")


class AgentToolService:
    """Agent 工具服务，负责内置工具注册、本次运行工具筛选和工具调试调用。"""

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
        for tool in JOB_TOOLS:
            self.registry.register(
                AgentToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    callable_ref=tool,
                )
            )
        logger.info("Agent built-in tools registered: names=%s", self.registry.list_tools())

    def _build_args_schema(self, tool: Any) -> dict[str, Any]:
        """提取 LangChain Tool 的参数 JSON Schema。

        Args:
            tool: LangChain Tool 或兼容工具对象。

        Returns:
            工具参数 JSON Schema；无法提取时返回空字典。
        """
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is not None and hasattr(args_schema, "model_json_schema"):
            return args_schema.model_json_schema()
        args = getattr(tool, "args", None)
        return args if isinstance(args, dict) else {}

    def _to_tool_info(self, definition: AgentToolDefinition) -> AgentToolInfo:
        """把内部工具定义转换成前端可展示的工具详情。

        Args:
            definition: 工具注册中心保存的工具定义。

        Returns:
            AgentToolInfo 工具详情。
        """
        return AgentToolInfo(
            name=definition.name,
            description=definition.description,
            group="regular",
            invokable=True,
            args_schema=self._build_args_schema(definition.callable_ref),
        )

    def _build_a2a_tool_info(self) -> AgentToolInfo:
        """构建 A2A 动态工具展示信息。

        Returns:
            A2A 工具详情；该工具依赖运行时 a2a.sub_agent_list，不允许直接调试调用。
        """
        return AgentToolInfo(
            name=a2a_call.name,
            description=a2a_call.description,
            group="a2a",
            invokable=False,
            invoke_note="A2A 工具由 /agent/run 在传入 a2a.sub_agent_list 时动态注入，不能脱离 Agent 运行上下文直接调试。",
            args_schema=self._build_args_schema(a2a_call),
        )

    def list_tools(self) -> list[str]:
        """
        查询当前注册的常规工具名称。

        Returns:
            常规工具名称列表，不包含动态 A2A 工具。
        """
        return self.registry.list_tools()

    def list_tool_details(self, include_dynamic: bool = True) -> list[AgentToolInfo]:
        """查询当前可展示的工具详情。

        Args:
            include_dynamic: 是否包含 A2A 这类动态工具说明。

        Returns:
            工具详情列表。
        """
        items = [self._to_tool_info(definition) for definition in self.registry.list_definitions()]
        if include_dynamic:
            items.append(self._build_a2a_tool_info())
        return items

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

    async def invoke_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        """调试调用一个常规 Agent 工具。

        Args:
            tool_name: 工具名称。
            args: 工具调用参数。

        Returns:
            工具执行结果。

        Raises:
            RuntimeError: 工具不存在或该工具不允许直接调试调用。
        """
        cleaned_name = tool_name.strip()
        if cleaned_name == a2a_call.name:
            raise BusinessException(code=400, msg="a2a_call 是动态工具，必须通过 /agent/run 的 a2a.sub_agent_list 启用，不能直接调试调用。")
        if not self.registry.has_tool(cleaned_name):
            raise BusinessException(code=404, msg=f"工具不存在或未注册: {cleaned_name}")

        tool = self.registry.get_tool(cleaned_name)
        if hasattr(tool, "ainvoke"):
            return await tool.ainvoke(args)
        if hasattr(tool, "invoke"):
            result = tool.invoke(args)
            if inspect.isawaitable(result):
                return await result
            return result
        if callable(tool):
            result = tool(**args)
            if inspect.isawaitable(result):
                return await result
            return result
        raise BusinessException(code=400, msg=f"工具不可调用: {cleaned_name}")
