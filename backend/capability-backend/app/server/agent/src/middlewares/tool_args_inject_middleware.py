"""工具参数注入中间件：为工具调用预留运行时参数注入能力。"""

import logging
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from app.server.agent.src.graph.state import CareerAgentState

logger = logging.getLogger(__name__)


class ToolArgsInjectMiddleware(AgentMiddleware[CareerAgentState]):
    """为工具调用预留运行时参数注入能力。

    第一版只保留拦截点，后续可根据工具定义里的 injected_args，
    从 runtime.context 或 state 注入 meta_internal_* 参数。
    """

    state_schema = CareerAgentState

    def __init__(self, enabled: bool = True):
        """初始化工具参数注入中间件。

        Args:
            enabled: 是否启用参数注入。
        """
        self.enabled = enabled

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """拦截异步工具调用，预留参数注入口。"""
        if not self.enabled:
            return await handler(request)

        # 第一版先保留拦截点。
        # 后续根据工具的 injected_args 配置从 runtime.context 或 state 注入参数。
        return await handler(request)
