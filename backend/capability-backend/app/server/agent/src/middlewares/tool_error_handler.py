import logging
from collections.abc import Awaitable, Callable
from typing import Any


logger = logging.getLogger(__name__)


def create_tool_error_handler_middleware() -> Any:
    """创建工具异常处理中间件。

    Returns:
        可传给 LangChain create_agent 的 AgentMiddleware 实例。
    """
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.messages import ToolMessage
    from langgraph.errors import GraphBubbleUp
    from langgraph.prebuilt.tool_node import ToolCallRequest
    from langgraph.types import Command

    from app.server.agent.src.graph.state import CareerAgentState

    class ToolErrorHandlerMiddleware(AgentMiddleware[CareerAgentState]):
        """把普通工具异常转换成 ToolMessage，避免整个 Agent 流程直接崩掉。"""

        # 声明该中间件使用的平台基础 state。
        # 后续可以把异常摘要写入 state.metadata 或 tool_trace，方便错误排查。
        state_schema = CareerAgentState

        def build_error_message(self, request: ToolCallRequest, error: Exception) -> ToolMessage:
            """根据工具异常构造错误 ToolMessage。

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
            """拦截异步工具调用异常。

            Args:
                request: LangChain 工具调用请求。
                handler: 原始工具调用处理器。

            Returns:
                工具调用结果，或表示错误的 ToolMessage。
            """
            try:
                return await handler(request)
            except GraphBubbleUp:
                # GraphBubbleUp 是 LangGraph 用于中断、跳转等控制流的异常，必须原样抛出。
                raise
            except Exception as error:
                logger.exception("Agent tool execution failed: name=%s", request.tool_call.get("name"))
                return self.build_error_message(request, error)

    return ToolErrorHandlerMiddleware()
