import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any


logger = logging.getLogger(__name__)


def create_tool_logging_middleware() -> Any:
    """创建工具调用日志中间件。

    Returns:
        可传给 LangChain create_agent 的 AgentMiddleware 实例。
    """
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.messages import ToolMessage
    from langgraph.prebuilt.tool_node import ToolCallRequest
    from langgraph.types import Command

    from app.server.agent.src.graph.state import CareerAgentState

    class ToolLoggingMiddleware(AgentMiddleware[CareerAgentState]):
        """记录工具调用入参和耗时。"""

        # 声明该中间件使用的平台基础 state。
        # create_agent 会读取 middleware.state_schema，并合并到底层 LangGraph 状态里。
        state_schema = CareerAgentState

        async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
        ) -> ToolMessage | Command:
            """拦截异步工具调用并记录耗时。

            Args:
                request: LangChain 工具调用请求。
                handler: 原始工具调用处理器。

            Returns:
                工具调用结果。
            """
            tool_call = request.tool_call
            start_time = time.time()

            # 这里先只写应用日志，不直接修改 state。
            # 后续如果要把工具轨迹持久化到 LangGraph state，可以返回 Command 更新 tool_trace。
            tool_args = tool_call.get("args") or {}
            logger.info(
                "Agent tool call start: name=%s arg_keys=%s",
                tool_call.get("name"),
                sorted(tool_args.keys()) if isinstance(tool_args, dict) else [],
            )
            response = await handler(request)
            logger.info("Agent tool call end: name=%s cost=%.3fs", tool_call.get("name"), time.time() - start_time)
            return response

    return ToolLoggingMiddleware()
