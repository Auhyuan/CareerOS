import inspect
import logging
from typing import Any

from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.server.agent.src.mcp import MCPService
from app.server.agent.src.tools.a2a_tool import a2a_call
from app.server.agent.src.tools.base import AgentToolDefinition
from app.server.agent.src.tools.planning_tools import set_task_plan, update_task_step
from app.server.agent.src.tools.registry import AgentToolRegistry
from app.server.agent.src.tools.schemas import AgentToolInfo

logger = logging.getLogger("ai_backend.agent.tools")


class AgentToolService:
    """Agent 工具服务，负责内置工具、MCP 工具和工具调试调用。"""

    def __init__(self, registry: AgentToolRegistry | None = None, mcp_service: MCPService | None = None):
        """初始化 Agent 工具服务。

        Args:
            registry: 可选工具注册表；不传时使用默认注册表。
            mcp_service: MCP 工具服务；不传时使用默认服务。
        """
        self.registry = registry or AgentToolRegistry()
        self.mcp_service = mcp_service or MCPService()
        if registry is None:
            self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """注册 AI-backend 内部工具。

        规划工具属于内部动态工具：
        - 工具管理页可以展示它们的参数和说明。
        - 真正运行时由 optional_features.planning_enabled 自动注入。
        - 因为依赖 LangGraph ToolRuntime.state，不允许在工具测试页直接调用。
        """
        self.registry.register(AgentToolDefinition(
            name=set_task_plan.name,
            description=set_task_plan.description or "创建或重写任务计划草稿，并触发用户确认。",
            callable_ref=set_task_plan,
        ))
        self.registry.register(AgentToolDefinition(
            name=update_task_step.name,
            description=update_task_step.description or "更新运行中任务计划的单个步骤。",
            callable_ref=update_task_step,
        ))

    def _build_args_schema(self, tool: Any) -> dict[str, Any]:
        """提取工具暴露给模型的参数 JSON Schema。

        Args:
            tool: LangChain tool 或兼容的可调用工具对象。

        Returns:
            工具参数 JSON Schema；无法提取时返回空字典。
        """
        # LangChain tool.args 通常已经过滤掉 ToolRuntime 等注入参数，优先使用它给前端展示。
        args = getattr(tool, "args", None)
        if isinstance(args, dict):
            return args

        args_schema = getattr(tool, "args_schema", None)
        if args_schema is not None and hasattr(args_schema, "model_json_schema"):
            try:
                return args_schema.model_json_schema()
            except Exception as error:  # noqa: BLE001
                logger.warning("工具参数 schema 构建失败: name=%s error=%s", getattr(tool, "name", "unknown"), error)
        return {}

    def _to_tool_info(self, definition) -> AgentToolInfo:
        """把内部工具定义转换为前端展示结构。

        Args:
            definition: 注册中心中的工具定义。

        Returns:
            工具管理页展示使用的 AgentToolInfo。
        """
        is_planning_tool = definition.name in {set_task_plan.name, update_task_step.name}
        return AgentToolInfo(
            name=definition.name,
            description=definition.description,
            group="planning" if is_planning_tool else "regular",
            invokable=not is_planning_tool,
            invoke_note="规划工具依赖 LangGraph 运行态，只能通过 /agent/run 的 planning_enabled 自动启用。" if is_planning_tool else None,
            args_schema=self._build_args_schema(definition.callable_ref),
        )

    def _build_a2a_tool_info(self) -> AgentToolInfo:
        """构建动态 A2A 工具的前端展示信息。

        Returns:
            A2A 工具元数据。该工具依赖运行时 a2a.sub_agent_list，不能在工具管理页直接测试。
        """
        return AgentToolInfo(
            name=a2a_call.name,
            description=a2a_call.description,
            group="a2a",
            invokable=False,
            invoke_note=(
                "a2a_call 会在 /agent/run 检测到 a2a.sub_agent_list 后动态注入，"
                "不能在工具测试页直接调用。"
            ),
            args_schema=self._build_args_schema(a2a_call),
        )

    def list_tools(self) -> list[str]:
        """查询 AI-backend 内置常规工具名称。"""
        return self.registry.list_tools()

    def list_tool_details(self, include_dynamic: bool = True) -> list[AgentToolInfo]:
        """查询前端可展示的内置工具详情。

        Args:
            include_dynamic: 是否包含 A2A 这类动态工具。

        Returns:
            工具元数据列表。MCP 外部工具请通过 /agent/mcp/search 查询。
        """
        items = [self._to_tool_info(definition) for definition in self.registry.list_definitions()]
        if include_dynamic:
            items.append(self._build_a2a_tool_info())
        return items

    async def get_tools(self, tool_names: list[str] | None = None, db: Session | None = None) -> list[Any]:
        """解析本次 Agent 运行可用的工具列表。

        Args:
            tool_names: 工具白名单。None 返回全部内置常规工具；空列表表示不加载常规工具。
            db: 数据库会话；当工具列表中包含 MCP 工具时必须传入。

        Returns:
            可传给 LangChain create_agent 的工具对象列表。
        """
        if tool_names is None:
            return self.registry.get_all_tools()
        if not tool_names:
            return []

        builtin_tool_names: list[str] = []
        mcp_tool_codes: list[str] = []
        for name in tool_names:
            if self.registry.has_tool(name):
                builtin_tool_names.append(name)
            else:
                mcp_tool_codes.append(name)

        tools = [self.registry.get_tool(name) for name in builtin_tool_names]
        if mcp_tool_codes:
            if db is not None:
                tools.extend(await self.mcp_service.load_langchain_tools(db, mcp_tool_codes))
            else:
                # A2A 子 Agent 等内部调用场景可能不传 db，此时短暂打开一个
                # 只读会话，仅用于加载 MCP 工具配置，不写业务会话记录。
                from app.common.db.postgres_db import get_db_session

                with get_db_session() as inner_db:
                    tools.extend(await self.mcp_service.load_langchain_tools(inner_db, mcp_tool_codes))
        return tools

    async def invoke_tool(self, tool_name: str, args: dict[str, Any], db: Session | None = None) -> Any:
        """从工具管理页测试调用一个工具。

        Args:
            tool_name: 工具名称或 MCP 工具编码。
            args: 工具调用参数。
            db: 数据库会话；调试调用 MCP 工具时必须传入。

        Returns:
            工具执行结果。
        """
        cleaned_name = tool_name.strip()
        if cleaned_name == a2a_call.name:
            raise BusinessException(
                code=400,
                msg="a2a_call 是动态工具，需要通过 /agent/run 的 A2A 配置启用，不能直接测试调用。",
            )
        if cleaned_name in {set_task_plan.name, update_task_step.name}:
            raise BusinessException(
                code=400,
                msg="规划工具依赖 LangGraph 运行态，请通过 /agent/run 开启 planning_enabled 后由 Agent 调用。",
            )
        if not self.registry.has_tool(cleaned_name):
            if db is None:
                raise BusinessException(code=404, msg=f"工具不存在或未注册: {cleaned_name}")
            try:
                mcp_tools = await self.mcp_service.load_langchain_tools(db, [cleaned_name])
            except RuntimeError as error:
                raise BusinessException(code=404, msg=str(error)) from error
            if not mcp_tools:
                raise BusinessException(code=404, msg=f"工具不存在或未注册: {cleaned_name}")
            return await mcp_tools[0].ainvoke(args)

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
