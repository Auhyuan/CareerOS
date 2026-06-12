import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any


logger = logging.getLogger(__name__)


def create_tool_logging_middleware() -> Any:
    """
    创建工具调用日志中间件。

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

    class ToolLoggingMiddleware(AgentMiddleware):
        """记录工具调用入参和耗时。"""

        async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
        ) -> ToolMessage | Command:
            """
            拦截异步工具调用并记录耗时。

            Args:
                request: LangChain 工具调用请求。
                handler: 原始工具调用处理器。

            Returns:
                工具调用结果。
            """
            tool_call = request.tool_call
            start_time = time.time()
            logger.info("Agent tool call start: %s", tool_call)
            response = await handler(request)
            logger.info("Agent tool call end: name=%s cost=%.3fs", tool_call.get("name"), time.time() - start_time)
            return response

    return ToolLoggingMiddleware()
