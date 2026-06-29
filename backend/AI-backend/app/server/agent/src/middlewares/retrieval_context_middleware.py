"""Middleware that injects retrieval tool results into the next model call."""

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
    """LangGraph state extension for retrieval context.

    Retrieval tools write results through Command(update={"retrieval_context": [...]}). The operator.add
    reducer allows multiple retrieval tool calls in one run to append context instead of overwriting it.
    """

    retrieval_context: NotRequired[Annotated[list[dict[str, str]], operator.add]]


class InjectRetrievalContextMiddleware(AgentMiddleware[RetrievalContextState]):
    """Inject current-run retrieval context into the system prompt before model calls.

    Checkpoint keeps state by thread_id. Because retrieval_context is temporary material for one Agent run,
    every item must carry run_id. This middleware only injects items whose run_id matches the current runtime
    context, preventing old retrieval results from polluting later user questions in the same conversation.
    """

    state_schema = RetrievalContextState

    def __init__(self, enabled: bool = True):
        """Initialize the retrieval context middleware.

        Args:
            enabled: Whether retrieval context injection is enabled.
        """
        self.enabled = enabled

    def _get_current_run_id(self, request: ModelRequest) -> str:
        """Read the current run_id from LangChain runtime context.

        Args:
            request: LangChain model request.

        Returns:
            Current Agent run ID. Returns an empty string when unavailable.
        """
        context = getattr(request.runtime, "context", None)
        if isinstance(context, dict):
            return str(context.get("run_id") or "")
        return str(getattr(context, "run_id", "") or "")

    def _filter_current_run_context(self, retrieval_context: object, current_run_id: str) -> list[str]:
        """Keep only retrieval context written by the current Agent run.

        Args:
            retrieval_context: Raw retrieval_context state value.
            current_run_id: Current Agent run ID.

        Returns:
            Retrieval context strings that can be injected into the system prompt.
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
        """Inject retrieval context before every model call.

        Args:
            request: LangChain model request.
            handler: Next model-call handler.

        Returns:
            Model response. When no current-run retrieval context exists, the request is passed through unchanged.
        """
        if not self.enabled:
            return await handler(request)

        # retrieval_context is stored in checkpoint state, so it must be filtered by run_id before injection.
        current_run_id = self._get_current_run_id(request)
        retrieval_context = (request.state or {}).get("retrieval_context", [])
        retrieval_context_items = self._filter_current_run_context(retrieval_context, current_run_id)
        if not retrieval_context_items:
            return await handler(request)

        logger.info(
            "检索上下文注入成功: run_id=%s items=%s",
            current_run_id,
            len(retrieval_context_items),
        )

        # Put retrieval material at the end of the system prompt so the base prompt keeps its priority and shape.
        joined_context = "\n\n---\n\n".join(retrieval_context_items)
        inserted = (
            "\n\n<retrieval_context>\n"
            f"{joined_context}\n\n"
            "Instruction: Use the retrieval context above when it is relevant. "
            "If the retrieved content is insufficient, say so honestly.\n"
            "</retrieval_context>"
        )
        current_prompt = getattr(request.system_message, "content", "")
        new_system = SystemMessage(content=f"{current_prompt}{inserted}")
        return await handler(request.override(system_message=new_system))
