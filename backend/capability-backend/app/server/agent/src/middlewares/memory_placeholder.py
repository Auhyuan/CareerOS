from collections.abc import Awaitable, Callable
from typing import Any


def create_memory_placeholder_middleware() -> Any:
    """创建长期记忆占位中间件。

    Returns:
        可传给 LangChain create_agent 的 AgentMiddleware 实例。
    """
    from langchain.agents.middleware import AgentMiddleware
    from langchain.agents.middleware.types import ModelRequest, ModelResponse

    from app.server.agent.src.graph.state import CareerAgentState

    class MemoryPlaceholderMiddleware(AgentMiddleware[CareerAgentState]):
        """长期记忆注入占位中间件。"""

        # 声明该中间件使用的平台基础 state。
        # 后续真正实现长期记忆时，可以在模型调用前后读取 messages 并写入记忆相关状态。
        state_schema = CareerAgentState

        async def awrap_model_call(
            self,
            request: ModelRequest,
            handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
        ) -> ModelResponse:
            """拦截模型调用，为后续长期记忆注入预留入口。

            Args:
                request: LangChain 模型调用请求。
                handler: 原始模型调用处理器。

            Returns:
                模型调用结果。
            """
            return await handler(request)

    return MemoryPlaceholderMiddleware()
