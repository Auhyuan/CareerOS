"""检索上下文注入中间件：将检索类工具的结果注入到 system prompt。"""

import logging
import operator
from collections.abc import Awaitable, Callable
from typing import Annotated

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage
from typing_extensions import NotRequired

from app.server.agent.src.graph.state import CareerAgentState

logger = logging.getLogger(__name__)


class RetrievalContextState(CareerAgentState, total=False):
    """检索上下文状态。

    检索类工具通过 Command(update={...}) 把检索结果写入 retrieval_context。
    这里使用 Annotated[list, operator.add] 是为了让多次工具调用可以追加内容，
    而不是后一次检索覆盖前一次检索。
    """

    retrieval_context: NotRequired[Annotated[list[dict[str, str]], operator.add]]


class InjectRetrievalContextMiddleware(AgentMiddleware[RetrievalContextState]):
    """将 state.retrieval_context 注入到 system prompt 的中间件。

    检索工具返回 Command(update={"retrieval_context": [{"run_id": "...", "content": "..."}]})，
    本中间件在下一轮模型调用前读取并注入到 system_message 尾部。

    注意：checkpoint 会按 thread_id 保留 state。为了避免同一会话下一轮问题读取到上一轮检索结果，
    每条检索内容都必须带 run_id，中间件只注入当前 run_id 对应的内容。
    """

    state_schema = RetrievalContextState

    def __init__(self, enabled: bool = True):
        """初始化检索上下文注入中间件。

        Args:
            enabled: 是否启用检索上下文注入。关闭时中间件直接透传请求。
        """
        self.enabled = enabled

    def _get_current_run_id(self, request: ModelRequest) -> str:
        """从 runtime context 中读取当前 run_id。

        Args:
            request: LangChain 模型调用请求。

        Returns:
            当前 Agent run 的唯一 ID。不存在时返回空字符串。
        """
        context = getattr(request.runtime, "context", None)
        if isinstance(context, dict):
            return str(context.get("run_id") or "")
        return str(getattr(context, "run_id", "") or "")

    def _filter_current_run_context(self, retrieval_context: object, current_run_id: str) -> list[str]:
        """只保留当前 run 写入的检索上下文。

        Args:
            retrieval_context: LangGraph state 中累积的检索上下文列表。
            current_run_id: 当前 Agent run 的 ID。

        Returns:
            当前 run 可注入到 system prompt 的检索内容列表。
        """
        if not isinstance(retrieval_context, list):
            return []

        items: list[str] = []
        for item in retrieval_context:
            if not isinstance(item, dict):
                continue
            if str(item.get("run_id") or "") != current_run_id:
                continue
            content = str(item.get("content") or "").strip()
            if content:
                items.append(content)
        return items

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """每次模型调用前检查并注入检索上下文。

        Args:
            request: LangChain 模型调用请求。
            handler: 后续模型调用处理器。

        Returns:
            模型调用结果。没有检索上下文时不修改请求。
        """
        if not self.enabled:
            return await handler(request)

        # Checkpointer 会保留同一个 thread_id 下的 state。
        # retrieval_context 属于“本次运行”的临时检索材料，所以必须按 run_id 过滤，
        # 避免上一轮用户问题的检索内容污染当前模型调用。
        current_run_id = self._get_current_run_id(request)
        retrieval_context = (request.state or {}).get("retrieval_context", [])
        retrieval_context_items = self._filter_current_run_context(retrieval_context, current_run_id)
        if not retrieval_context_items:
            return await handler(request)

        # 多次检索结果之间用分隔线隔开，让模型能识别它们是不同来源或不同查询结果。
        joined_context = "\n\n---\n\n".join(retrieval_context_items)
        inserted = (
            f"\n\n<knowledge_instruct>\n{joined_context}\n\n"
            f"# 回答要求：基于以上检索内容回答，若检索内容不足以回答问题请如实说明。\n"
            f"</knowledge_instruct>"
        )
        current_prompt = getattr(request.system_message, "content", "")
        new_system = SystemMessage(content=f"{current_prompt}{inserted}")
        return await handler(request.override(system_message=new_system))
