from collections.abc import Awaitable, Callable
from typing import Any


def create_tool_args_inject_middleware() -> Any:
    """
    创建工具参数注入中间件。

    Returns:
        LangChain AgentMiddleware 实例。
    """
    try:
        from langchain.agents.middleware import AgentMiddleware
        from langchain_core.messages import ToolMessage
        from langgraph.prebuilt.tool_node import ToolCallRequest
        from langgraph.types import Command
    except ImportError as error:
        raise RuntimeError("缺少 LangChain 中间件依赖，请先执行：pip install -r requirements.txt") from error

    class ToolArgsInjectMiddleware(AgentMiddleware):
        """为工具调用预留运行时参数注入能力。"""

        async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
        ) -> ToolMessage | Command:
            """
            拦截工具调用并注入运行时参数。

            Args:
                request: LangChain 工具调用请求。
                handler: 原始工具调用处理器。

            Returns:
                工具调用结果。
            """
            # 第一版先保留拦截点，后续会根据工具定义里的 injected_args 注入 meta_intern_。
            return await handler(request)

    return ToolArgsInjectMiddleware()
