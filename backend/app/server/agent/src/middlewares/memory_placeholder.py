from collections.abc import Awaitable, Callable
from typing import Any


def create_memory_placeholder_middleware() -> Any:
    """
    创建记忆中间件占位实现。

    Returns:
        LangChain AgentMiddleware 实例。
    """
    try:
        from langchain.agents.middleware import AgentMiddleware
        from langchain.agents.middleware.types import ModelRequest, ModelResponse
    except ImportError as error:
        raise RuntimeError("缺少 LangChain 中间件依赖，请先执行：pip install -r requirements.txt") from error

    class MemoryPlaceholderMiddleware(AgentMiddleware):
        """记忆注入占位中间件。"""

        async def awrap_model_call(
            self,
            request: ModelRequest,
            handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
        ) -> ModelResponse:
            """
            拦截模型调用，为后续记忆注入预留入口。

            Args:
                request: LangChain 模型调用请求。
                handler: 原始模型调用处理器。

            Returns:
                模型调用结果。
            """
            return await handler(request)

    return MemoryPlaceholderMiddleware()
