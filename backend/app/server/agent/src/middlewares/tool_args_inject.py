from collections.abc import Awaitable, Callable
from typing import Any


def create_tool_args_inject_middleware() -> Any:
    """创建工具参数注入中间件。

    Returns:
        可传给 LangChain create_agent 的 AgentMiddleware 实例。
    """
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.messages import ToolMessage
    from langgraph.prebuilt.tool_node import ToolCallRequest
    from langgraph.types import Command

    from app.server.agent.src.graph.state import CareerAgentState

    class ToolArgsInjectMiddleware(AgentMiddleware[CareerAgentState]):
        """为工具调用预留运行时参数注入能力。"""

        # 声明该中间件使用的平台基础 state。
        # 参数注入优先读取 runtime context，必要时也可以读取或更新 LangGraph state。
        state_schema = CareerAgentState

        async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
        ) -> ToolMessage | Command:
            """拦截工具调用并预留参数注入口。

            Args:
                request: LangChain 工具调用请求。
                handler: 原始工具调用处理器。

            Returns:
                工具调用结果。
            """
            # 第一版先保留拦截点。
            # 后续会根据工具定义里的 injected_args，从 runtime.context 或 state 注入 meta_internal_* 参数。
            return await handler(request)

    return ToolArgsInjectMiddleware()
