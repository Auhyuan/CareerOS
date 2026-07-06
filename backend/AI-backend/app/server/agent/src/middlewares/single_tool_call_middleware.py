"""限制单轮模型响应最多保留一个工具调用。"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class SingleToolCallMiddleware(AgentMiddleware[AgentState]):
    """裁剪模型并发工具调用，避免同一 LangGraph step 内多个工具同时写 state。"""

    def __init__(self, enabled: bool = True):
        """初始化单工具调用限制中间件。"""
        self.enabled = enabled


    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """在模型调用前注入单工具顺序调用规则。

        Args:
            request: LangChain 模型调用请求。
            handler: 后续模型调用处理器。

        Returns:
            模型调用结果。
        """
        if not self.enabled:
            return await handler(request)

        rule_prompt = (
            "<single_tool_call_rule>\n"
            "工具调用规则：调用工具时必须一个一个调用。"
            "等待当前工具执行完成并看到工具结果后，再决定是否调用下一个工具。"
            "不要在同一轮模型响应中并行发起多个工具调用。\n"
            "</single_tool_call_rule>"
        )
        current_prompt = getattr(request.system_message, "content", "")
        new_system = SystemMessage(content=f"{current_prompt}\n\n{rule_prompt}")
        return await handler(request.override(system_message=new_system))

    def _clip_tool_calls(self, state: AgentState) -> dict[str, Any] | None:
        """检查最后一条 AI 消息，若存在多个工具调用则只保留第一个。"""
        if not self.enabled:
            return None

        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        tool_calls = getattr(last_msg, "tool_calls", None) or []
        if len(tool_calls) <= 1:
            return None

        kept_tool_call = tool_calls[0]
        dropped_tool_calls = tool_calls[1:]
        logger.warning(
            "检测到模型单轮返回多个工具调用，已裁剪为只执行第一个工具: kept=%s, dropped=%s",
            kept_tool_call,
            dropped_tool_calls,
        )

        # 保持原消息 id 不变，让 messages reducer 用裁剪后的消息替换原 AIMessage。
        clipped_msg = last_msg.model_copy(update={"tool_calls": [kept_tool_call]})

        # 部分模型适配器会在 additional_kwargs 中保留原始 tool_calls，这里同步裁剪，避免后续节点读取到旧数据。
        additional_kwargs = dict(getattr(clipped_msg, "additional_kwargs", {}) or {})
        if "tool_calls" in additional_kwargs:
            additional_kwargs["tool_calls"] = additional_kwargs["tool_calls"][:1]
            clipped_msg = clipped_msg.model_copy(update={"additional_kwargs": additional_kwargs})

        return {"messages": [clipped_msg]}

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """同步模型调用结束后触发，用于裁剪并发工具调用。"""
        return self._clip_tool_calls(state)

    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """异步模型调用结束后触发，用于裁剪并发工具调用。"""
        return self._clip_tool_calls(state)
