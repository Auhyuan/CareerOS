import inspect
import logging
from typing import Any

from app.common.core.exceptions import BusinessException
from app.server.agent.src.tools.a2a_tool import a2a_call
from app.server.agent.src.tools.base import AgentToolDefinition
from app.server.agent.src.tools.job_tools import JOB_TOOLS
from app.server.agent.src.tools.registry import AgentToolRegistry
from app.server.agent.src.tools.schemas import AgentToolInfo

logger = logging.getLogger("ai_backend.agent.tools")


class AgentToolService:
    """Service for built-in Agent tools, tool filtering, and tool test invocation."""

    def __init__(self, registry: AgentToolRegistry | None = None):
        """Initialize the Agent tool service.

        Args:
            registry: Optional tool registry. When omitted, built-in platform tools are registered automatically.
        """
        self.registry = registry or AgentToolRegistry()
        if registry is None:
            self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register built-in platform tools used by Agent runs.

        Job tools call orchestration-backend APIs only. They must not directly access the Job database,
        otherwise AI-backend and orchestration-backend would become tightly coupled.
        """
        for tool in JOB_TOOLS:
            self.registry.register(
                AgentToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    callable_ref=tool,
                )
            )
        logger.info("内置工具注册完成: names=%s", self.registry.list_tools())

    def _build_args_schema(self, tool: Any) -> dict[str, Any]:
        """Extract the model-facing JSON schema for a LangChain tool.

        Args:
            tool: LangChain tool or compatible callable object.

        Returns:
            Tool argument JSON schema. Returns an empty dict when no schema can be extracted.
        """
        # LangChain tool.args is already filtered to the model-facing arguments. Prefer it because args_schema may
        # still contain injected runtime fields such as ToolRuntime, which cannot be rendered as JSON Schema.
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

    def _to_tool_info(self, definition: AgentToolDefinition) -> AgentToolInfo:
        """Convert an internal tool definition into frontend-friendly tool metadata.

        Args:
            definition: Tool definition stored in the registry.

        Returns:
            AgentToolInfo used by the tool management page.
        """
        return AgentToolInfo(
            name=definition.name,
            description=definition.description,
            group="regular",
            invokable=True,
            args_schema=self._build_args_schema(definition.callable_ref),
        )

    def _build_a2a_tool_info(self) -> AgentToolInfo:
        """Build metadata for the dynamic A2A tool.

        Returns:
            A2A tool metadata. This tool depends on runtime a2a.sub_agent_list and cannot be tested directly.
        """
        return AgentToolInfo(
            name=a2a_call.name,
            description=a2a_call.description,
            group="a2a",
            invokable=False,
            invoke_note=(
                "a2a_call is injected dynamically by /agent/run when a2a.sub_agent_list is provided; "
                "it cannot be invoked directly from the tool test page."
            ),
            args_schema=self._build_args_schema(a2a_call),
        )

    def list_tools(self) -> list[str]:
        """List names of regular registered tools.

        Returns:
            Regular tool names, excluding dynamic A2A tools.
        """
        return self.registry.list_tools()

    def list_tool_details(self, include_dynamic: bool = True) -> list[AgentToolInfo]:
        """List frontend-displayable tool details.

        Args:
            include_dynamic: Whether to include dynamic tools such as A2A in the returned metadata.

        Returns:
            Tool metadata list.
        """
        items = [self._to_tool_info(definition) for definition in self.registry.list_definitions()]
        if include_dynamic:
            items.append(self._build_a2a_tool_info())
        return items

    def get_tools(self, tool_names: list[str] | None = None) -> list[Any]:
        """Resolve tools available to the current Agent run.

        Args:
            tool_names: Tool allowlist. None returns all regular tools; an empty list disables regular tools.

        Returns:
            Tool objects that can be passed to LangChain create_agent.

        Raises:
            RuntimeError: Raised when the request contains an unknown tool name.
        """
        if tool_names is None:
            return self.registry.get_all_tools()
        if not tool_names:
            return []

        missing_names = [name for name in tool_names if not self.registry.has_tool(name)]
        if missing_names:
            raise RuntimeError(f"Agent requested unregistered tools: {', '.join(missing_names)}")
        return [self.registry.get_tool(name) for name in tool_names]

    async def invoke_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Invoke a regular tool from the tool management test API.

        Args:
            tool_name: Tool name.
            args: Tool invocation arguments.

        Returns:
            Tool execution result.

        Raises:
            BusinessException: Raised when the tool does not exist, is dynamic-only, or cannot be invoked directly.
        """
        cleaned_name = tool_name.strip()
        if cleaned_name == a2a_call.name:
            raise BusinessException(
                code=400,
                msg="a2a_call is a dynamic tool and must be enabled through /agent/run a2a options.",
            )
        if not self.registry.has_tool(cleaned_name):
            raise BusinessException(code=404, msg=f"Tool is not registered: {cleaned_name}")

        # search_job_skills is a LangGraph state-updating tool in real Agent runs. Direct test calls do not have
        # ToolRuntime, so the management API uses a runtime-free helper that returns the raw Job API result.
        if cleaned_name == "search_job_skills":
            from app.server.agent.src.tools.job_tools.job_skill import query_job_skills_data

            raw_keywords = args.get("keywords") if isinstance(args, dict) else None
            if not isinstance(raw_keywords, list):
                raise BusinessException(code=400, msg="search_job_skills requires keywords: list[str].")
            return await query_job_skills_data(raw_keywords)

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
        raise BusinessException(code=400, msg=f"Tool is not invokable: {cleaned_name}")
