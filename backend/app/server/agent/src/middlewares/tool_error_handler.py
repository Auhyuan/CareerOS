import logging
from collections.abc import Awaitable, Callable
from typing import Any


logger = logging.getLogger(__name__)


def create_tool_error_handler_middleware() -> Any:
    """
    创建工具异常处理中间件。

    Returns:
        LangChain AgentMiddleware 实例。
    """
    try:
        from langchain.agents.middleware import AgentMiddleware
        from langchain_core.messages import ToolMessage
        from langgraph.errors import GraphBubbleUp
        from langgraph.prebuilt.tool_node import ToolCallRequest
        from langgraph.types import Command
    except ImportError as error:
        raise RuntimeError("缺少 LangChain 中间件依赖，请先执行：pip install -r requirements.txt") from error

    class ToolErrorHandlerMiddleware(AgentMiddleware):
        """把工具异常转换成 ToolMessage，避免整个 Agent 流程直接崩掉。"""

        def build_error_message(self, request: ToolCallRequest, error: Exception) -> ToolMessage:
            """
            根据工具异常构造错误 ToolMessage。

            Args:
                request: LangChain 工具调用请求。
                error: 工具执行异常。

            Returns:
                表示工具执行失败的 ToolMessage。
            """
            tool_name = str(request.tool_call.get("name") or "unknown_tool")
            tool_call_id = str(request.tool_call.get("id") or "missing_tool_call_id")
            detail = str(error).strip() or error.__class__.__name__
            if len(detail) > 500:
                detail = detail[:497] + "..."
            return ToolMessage(
                content=f"Error: Tool '{tool_name}' failed with {error.__class__.__name__}: {detail}",
                tool_call_id=tool_call_id,
                name=tool_name,
                status="error",
            )

        async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
        ) -> ToolMessage | Command:
            """
            拦截异步工具调用异常。

            Args:
                request: LangChain 工具调用请求。
                handler: 原始工具调用处理器。

            Returns:
                工具调用结果或错误 ToolMessage。
            """
            try:
                return await handler(request)
            except GraphBubbleUp:
                raise
            except Exception as error:
                logger.exception("Agent tool execution failed: name=%s", request.tool_call.get("name"))
                return self.build_error_message(request, error)

    return ToolErrorHandlerMiddleware()
