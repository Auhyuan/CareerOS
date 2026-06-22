from langchain.agents import create_agent
from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from sqlmodel import Session

from app.server.agent.src.agent.assembly import AgentAssembly
from app.server.agent.src.checkpoint import AgentCheckpointService
from app.server.agent.src.context import AgentContextService
from app.server.agent.src.memory import AgentMemoryService
from app.server.agent.src.middlewares import MiddlewareFactory
from app.server.agent.src.model import AgentModelService
from app.server.agent.src.prompts import DEFAULT_AGENT_SYSTEM_PROMPT, AgentPromptService
from app.server.agent.src.runtime import AgentRuntimeContext, AgentRuntimeContextService
from app.server.agent.src.schemas.config import AgentBuildConfig, AgentFeatureConfig
from app.server.agent.src.schemas.request import AgentRunRequest
from app.server.agent.src.schemas.response import AgentRunResponse
from app.server.agent.src.tools import AgentToolService


class AgentService:
    """平台通用 Agent 服务，负责把模型、工具、prompt、中间件和 checkpointer 组装起来。"""

    def __init__(
        self,
        *,
        model_service: AgentModelService | None = None,
        tool_service: AgentToolService | None = None,
        prompt_service: AgentPromptService | None = None,
        runtime_context_service: AgentRuntimeContextService | None = None,
        middleware_factory: MiddlewareFactory | None = None,
        memory_service: AgentMemoryService | None = None,
        checkpoint_service: AgentCheckpointService | None = None,
        context_service: AgentContextService | None = None,
    ):
        """初始化平台通用 Agent 服务。

        Args:
            model_service: 模型服务，负责创建 ChatOpenAI 等模型实例。
            tool_service: 工具服务，负责按工具名筛选本次可用工具。
            prompt_service: Prompt 服务，负责渲染系统提示词。
            runtime_context_service: 运行时上下文服务，负责构建 thread_id、inputs 等上下文。
            middleware_factory: 中间件工厂，负责返回本次需要装配的中间件。
            memory_service: 记忆服务，当前先预留长期记忆能力。
            checkpoint_service: Checkpointer 服务，负责 LangGraph 状态持久化。
            context_service: 历史会话服务，负责读写 agent_conversations 和 agent_messages。
        """
        self.model_service = model_service or AgentModelService()
        self.tool_service = tool_service or AgentToolService()
        self.prompt_service = prompt_service or AgentPromptService()
        self.runtime_context_service = runtime_context_service or AgentRuntimeContextService()
        self.middleware_factory = middleware_factory or MiddlewareFactory()
        self.memory_service = memory_service or AgentMemoryService()
        self.checkpoint_service = checkpoint_service or AgentCheckpointService()
        self.context_service = context_service or AgentContextService()

    def build_agent_assembly_config(self, request: AgentRunRequest) -> AgentBuildConfig:
        """组装本次 Agent 运行需要的内部配置。

        Args:
            request: 通用 Agent 运行请求。

        Returns:
            AgentBuildConfig，本次 Agent 装配配置。
        """
        # API 层暴露的是 optional_features 这种业务能力参数；
        # Agent 内部真正关心的是是否装配对应中间件或运行能力。
        features = AgentFeatureConfig(
            enable_memory=request.optional_features.long_term_memory_enabled,
            enable_deferred_tool_filter=request.optional_features.deferred_tool_filter_enabled,
            enable_checkpointer=request.optional_features.checkpoint_enabled,
        )

        return AgentBuildConfig(
            system_prompt=request.system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT,
            response_format=request.response_format,
            tool_names=request.tools,
            features=features,
        )

    async def assemble_agent(
        self,
        request: AgentRunRequest,
        context: AgentRuntimeContext,
    ) -> AgentAssembly:
        """组装 LangChain Agent。

        Args:
            request: 通用 Agent 运行请求。
            context: Agent 运行上下文。

        Returns:
            AgentAssembly，包含已组装的 agent、model、tools、middlewares 和调试元数据。
        """
        # 第一步：生成本次装配配置。
        build_config = self.build_agent_assembly_config(request)

        # 第二步：渲染系统提示词。
        system_prompt = self.prompt_service.render_system_prompt(
            build_config.system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT,
            context.inputs,
        )

        # 第三步：按工具白名单加载本次可用工具。
        tools = self.tool_service.get_tools(build_config.tool_names)

        # 第四步：构建 LangChain runtime context schema。
        context_schema = self.runtime_context_service.get_context_schema()

        # 第五步：创建中间件实例，并提取中间件声明的 LangGraph state schema。
        middlewares = self.middleware_factory.build_langchain_middlewares(build_config.features)
        middleware_names = self.middleware_factory.describe_middlewares(build_config.features)
        state_schema_names = self.middleware_factory.describe_state_schemas(middlewares)

        # 第六步：创建聊天模型。
        model = self.model_service.create_chat_model(
            model=request.runtime_options.model,
            temperature=request.runtime_options.temperature,
            timeout_seconds=request.runtime_options.timeout_seconds,
            max_retries=request.runtime_options.max_retries,
        )

        # 第七步：按需获取 LangGraph checkpointer。
        # Checkpointer 保存的是 LangGraph 图状态，不替代 ContextService 的历史消息表。
        checkpointer = None
        if build_config.features.enable_checkpointer:
            checkpointer = await self.checkpoint_service.get_checkpointer()

        # 第八步：真正创建 LangChain Agent。
        agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            response_format=build_config.response_format,
            context_schema=context_schema,
            middleware=middlewares,
            checkpointer=checkpointer,
        )

        return AgentAssembly(
            agent=agent,
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            context_schema=context_schema,
            middlewares=middlewares,
            context=context,
            metadata={
                "tool_count": len(tools),
                "tools": [getattr(tool, "name", tool.__class__.__name__) for tool in tools],
                "middlewares": middleware_names,
                "context_schema": context_schema.__name__,
                "state_schemas": state_schema_names,
                "checkpointer_enabled": checkpointer is not None,
                "structured_output_enabled": build_config.response_format is not None,
            },
        )

    async def run(self, request: AgentRunRequest, db: Session | None = None) -> AgentRunResponse:
        """运行通用 Agent。

        Args:
            request: 通用 Agent 运行请求。
            db: PostgreSQL Session。API 调用场景会传入，非 Web 场景可以为空。

        Returns:
            AgentRunResponse，包含最终回答和结构化输出。
        """
        # 第一步：构建运行时上下文。
        context = self.runtime_context_service.build_context(request)

        # 第二步：如果开启会话上下文，就从数据库读取最近历史消息。
        context_enabled = request.optional_features.conversation_context_enabled and db is not None
        history_messages = []
        if context_enabled:
            self.context_service.ensure_conversation(
                db,
                conversation_id=context.thread_id,
                metadata={},
            )
            recent_messages = self.context_service.get_recent_messages(
                db,
                conversation_id=context.thread_id,
                limit=20,
            )
            history_messages = self.context_service.to_langchain_messages(recent_messages)

        # 第三步：组装 Agent。
        assembly = await self.assemble_agent(request, context)

        # 第四步：组装传给 LangChain 的消息。
        # 如果启用了 checkpointer，同一个 thread_id 可能会恢复出旧的 state.messages。
        # 这里参考 agent_engine 的做法，先清空 checkpoint 中的旧 messages，
        # 再注入 ContextService 构建的历史消息和本轮用户消息，确保历史来源只有 ContextService。
        input_messages = [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *history_messages,
            {"role": "user", "content": request.query},
        ]

        # 第五步：运行前写入用户消息。
        if context_enabled:
            self.context_service.add_user_message(
                db,
                conversation_id=context.thread_id,
                content=request.query,
                metadata={},
            )

        # 第六步：真实调用 Agent。
        result = await assembly.agent.ainvoke(
            {"messages": input_messages},
            config={"configurable": {"thread_id": context.thread_id}, "recursion_limit": 50},
            context=context.to_langchain_context(),
        )

        # 第七步：提取最终回答。
        answer = result["messages"][-1].content if result.get("messages") else ""

        # 第八步：交给长期记忆服务处理。当前 MemoryService 还是占位实现。
        await self.memory_service.save_interaction(context, answer)

        # 第九步：运行后写入 Agent 回复。
        if context_enabled:
            self.context_service.add_assistant_message(
                db,
                conversation_id=context.thread_id,
                content=answer,
                metadata={},
            )

        return AgentRunResponse(
            answer=answer,
            structured_output=result.get("structured_response") or result.get("structured_output"),
        )
