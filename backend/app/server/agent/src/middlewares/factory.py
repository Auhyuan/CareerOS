from app.server.agent.src.schemas.config import AgentFeatureConfig


class MiddlewareFactory:
    """Agent 中间件工厂。"""

    def build_langchain_middlewares(self, features: AgentFeatureConfig | None = None) -> list[object]:
        """
        根据内部能力配置创建 LangChain AgentMiddleware 列表。

        Args:
            features: Agent 内部装配能力开关。

        Returns:
            可传给 LangChain create_agent(middleware=...) 的中间件列表。
        """
        current_features = features or AgentFeatureConfig()
        middlewares: list[object] = []

        # 基础能力：工具异常处理。默认开启，避免工具报错直接打断整个 Agent 流程。
        if current_features.enable_tool_error_handler:
            from app.server.agent.src.middlewares.tool_error_handler import create_tool_error_handler_middleware

            middlewares.append(create_tool_error_handler_middleware())

        # 基础能力：工具参数注入。默认开启，只有工具声明注入参数时才会真正生效。
        if current_features.enable_tool_args_injection:
            from app.server.agent.src.middlewares.tool_args_inject import create_tool_args_inject_middleware

            middlewares.append(create_tool_args_inject_middleware())

        # 基础能力：工具调用日志。默认开启，方便后续排查 agent 为什么调用了某个工具。
        if current_features.enable_tool_logging:
            from app.server.agent.src.middlewares.tool_logging import create_tool_logging_middleware

            middlewares.append(create_tool_logging_middleware())

        # 可选能力：长期记忆。只有 API 的 optional_features.long_term_memory_enabled 为 true 时才装配。
        if current_features.enable_memory:
            from app.server.agent.src.middlewares.memory_placeholder import create_memory_placeholder_middleware

            middlewares.append(create_memory_placeholder_middleware())

        return middlewares

    def describe_middlewares(self, features: AgentFeatureConfig | None = None) -> list[str]:
        """
        返回当前内部能力配置下会启用的中间件名称。

        Args:
            features: Agent 内部装配能力开关。

        Returns:
            中间件名称列表。
        """
        current_features = features or AgentFeatureConfig()
        names: list[str] = []
        if current_features.enable_tool_error_handler:
            names.append("ToolErrorHandlerMiddleware")
        if current_features.enable_tool_args_injection:
            names.append("ToolArgsInjectMiddleware")
        if current_features.enable_tool_logging:
            names.append("ToolLoggingMiddleware")
        if current_features.enable_memory:
            names.append("MemoryPlaceholderMiddleware")
        if current_features.enable_deferred_tool_filter:
            names.append("DeferredToolFilterMiddleware")
        return names
