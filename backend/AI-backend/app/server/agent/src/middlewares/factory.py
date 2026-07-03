from app.server.agent.src.middlewares.a2a_context_middleware import A2AAgentContextMiddleware
from app.server.agent.src.middlewares.interrupt_middleware import InterruptMiddleware
from app.server.agent.src.middlewares.memory_placeholder_middleware import MemoryPlaceholderMiddleware
from app.server.agent.src.middlewares.retrieval_context_middleware import InjectRetrievalContextMiddleware
from app.server.agent.src.middlewares.single_tool_call_middleware import SingleToolCallMiddleware
from app.server.agent.src.middlewares.tool_args_inject_middleware import ToolArgsInjectMiddleware
from app.server.agent.src.middlewares.tool_error_handler_middleware import ToolErrorHandlerMiddleware
from app.server.agent.src.middlewares.tool_logging_middleware import ToolLoggingMiddleware
from app.server.agent.src.schemas.config import AgentFeatureConfig


class MiddlewareFactory:
    """Agent 中间件工厂。"""

    def build_langchain_middlewares(self, features: AgentFeatureConfig | None = None) -> list[object]:
        """根据内部能力配置创建 LangChain AgentMiddleware 列表。

        Args:
            features: Agent 内部装配能力开关。

        Returns:
            可传给 LangChain create_agent(middleware=...) 的中间件列表。
        """
        current_features = features or AgentFeatureConfig()
        middlewares: list[object] = []

        # 基础能力：单工具调用限制。默认开启，避免模型并发调用多个工具时写 state 冲突。
        middlewares.append(SingleToolCallMiddleware())

        # 基础能力：工具异常处理。始终开启，避免普通工具报错直接打断整个 Agent 流程。
        middlewares.append(ToolErrorHandlerMiddleware())

        # 基础能力：工具参数注入。默认开启，只有工具声明注入参数时才真正生效。
        middlewares.append(ToolArgsInjectMiddleware())

        # 基础能力：工具调用日志。默认开启，方便后续排查 Agent 为什么调用了某个工具。
        middlewares.append(ToolLoggingMiddleware())

        # 基础能力：通用中断。默认开启，但只有 state.interrupt_enabled=true 时才真正触发。
        middlewares.append(InterruptMiddleware())

        # 可选能力：长期记忆。只有 API 的 optional_features.long_term_memory_enabled 为 true 时才装配。
        if current_features.enable_memory:
            middlewares.append(MemoryPlaceholderMiddleware())

        # 检索上下文注入：默认始终装配。无检索内容时该中间件 no-op。
        middlewares.append(InjectRetrievalContextMiddleware())

        # A2A 上下文注入：默认始终装配。无 sub_agent_list 时该中间件 no-op。
        middlewares.append(A2AAgentContextMiddleware())

        return middlewares

    def describe_middlewares(self, features: AgentFeatureConfig | None = None) -> list[str]:
        """返回当前内部能力配置下会启用的中间件名称。

        Args:
            features: Agent 内部装配能力开关。

        Returns:
            中间件名称列表。
        """
        current_features = features or AgentFeatureConfig()
        names: list[str] = [
            "SingleToolCallMiddleware",
            "ToolErrorHandlerMiddleware",
            "ToolArgsInjectMiddleware",
            "ToolLoggingMiddleware",
            "InterruptMiddleware",
        ]
        if current_features.enable_memory:
            names.append("MemoryPlaceholderMiddleware")
        names.append("InjectRetrievalContextMiddleware")
        names.append("A2AAgentContextMiddleware")

        return names

    def describe_state_schemas(self, middlewares: list[object]) -> list[str]:
        """返回中间件声明的 LangGraph state schema 名称。

        Args:
            middlewares: 已创建的 LangChain AgentMiddleware 实例列表。

        Returns:
            去重后的 state schema 名称列表。
        """
        state_schema_names: list[str] = []

        for middleware in middlewares:
            state_schema = getattr(middleware, "state_schema", None)
            if state_schema is None:
                continue

            state_schema_name = getattr(state_schema, "__name__", str(state_schema))
            if state_schema_name not in state_schema_names:
                state_schema_names.append(state_schema_name)

        return state_schema_names
