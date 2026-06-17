from app.server.agent.src.runtime.context import AgentRuntimeContext


class AgentMiddleware:
    """Agent 中间件基类。"""

    async def before_run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        """
        Agent 运行前处理上下文。

        Args:
            context: 当前运行上下文。

        Returns:
            处理后的运行上下文。
        """
        return context

    async def after_run(self, context: AgentRuntimeContext, result: object) -> object:
        """
        Agent 运行后处理结果。

        Args:
            context: 当前运行上下文。
            result: Agent 运行结果。

        Returns:
            处理后的运行结果。
        """
        return result


class AgentMiddlewareChain:
    """Agent 中间件链占位实现。"""

    def __init__(self, middlewares: list[AgentMiddleware] | None = None):
        """
        初始化中间件链。

        Args:
            middlewares: 中间件列表。
        """
        self.middlewares = middlewares or []

    async def apply_before_run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        """
        顺序执行所有 before_run 钩子。

        Args:
            context: 当前运行上下文。

        Returns:
            处理后的运行上下文。
        """
        current_context = context
        for middleware in self.middlewares:
            current_context = await middleware.before_run(current_context)
        return current_context

    async def apply_after_run(self, context: AgentRuntimeContext, result: object) -> object:
        """
        逆序执行所有 after_run 钩子。

        Args:
            context: 当前运行上下文。
            result: Agent 运行结果。

        Returns:
            处理后的运行结果。
        """
        current_result = result
        for middleware in reversed(self.middlewares):
            current_result = await middleware.after_run(context, current_result)
        return current_result
