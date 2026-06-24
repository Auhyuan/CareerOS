"""检索上下文注入中间件：将检索类工具的结果注入到 system prompt。"""

import logging
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage
from typing_extensions import NotRequired

from app.server.agent.src.graph.state import CareerAgentState

logger = logging.getLogger(__name__)


class RetrievalContextState(CareerAgentState, total=False):
    """检索上下文状态。

    由检索类工具通过 Command 写入，中间件读取后注入到 system prompt。
    """
    retrieval_context: NotRequired[str]


class InjectRetrievalContextMiddleware(AgentMiddleware[RetrievalContextState]):
    """将 state.retrieval_context 注入到 system prompt 的中间件。

    检索工具返回 Command(update={"retrieval_context": "..."})，
    本中间件在下一轮模型调用前读取并注入到 system_message 尾部。
    无检索内容时完全 no-op。
    """

    state_schema = RetrievalContextState

    def __init__(self, enabled: bool = True):
        """初始化检索上下文注入中间件。

        Args:
            enabled: 是否启用检索上下文注入。
        """
        self.enabled = enabled

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """每次模型调用前，检查并注入检索上下文。"""
        if not self.enabled:
            return await handler(request)

        retrieval_context = (request.state or {}).get("retrieval_context", "")
        if not retrieval_context:
            return await handler(request)

        inserted = (
            f"\n\n<knowledge_instruct>\n{retrieval_context}\n\n"
            f"# 回答要求：基于以上检索内容回答，若检索内容不足以回答问题请如实说明。\n"
            f"</knowledge_instruct>"
        )
        current_prompt = getattr(request.system_message, "content", "")
        new_system = SystemMessage(content=f"{current_prompt}{inserted}")
        return await handler(request.override(system_message=new_system))
