import logging
import time

from langchain.agents import create_agent

from app.server.agent.src.agent.assembly import AgentAssembly
from app.server.agent.src.checkpoint import AgentCheckpointService
from app.server.agent.src.middlewares import MiddlewareFactory
from app.server.agent.src.model import AgentModelService
from app.server.agent.src.prompts import DEFAULT_AGENT_SYSTEM_PROMPT, AgentPromptService
from app.server.agent.src.runtime import AgentRuntimeContext, AgentRuntimeContextService
from app.server.agent.src.schemas.config import AgentBuildConfig, AgentFeatureConfig
from app.server.agent.src.schemas.request import AgentRunRequest
from app.server.agent.src.tools import AgentToolService


logger = logging.getLogger("capability.agent.assembler")


class AgentAssembler:
    """Agent 组装器，负责完整的 Agent 装配流程。

    组装流程是一个不可拆分的整体：
    构建配置 → 渲染提示词 → 加载工具 → 构建上下文 schema →
    创建中间件 → 创建模型 → 获取 checkpointer → 调用 create_agent()。

    所有步骤按顺序执行，不暴露中间产物，外部只需传入请求和上下文即可获得
    完整的 AgentAssembly。
    """

    def __init__(
        self,
        *,
        model_service: AgentModelService | None = None,
        tool_service: AgentToolService | None = None,
        prompt_service: AgentPromptService | None = None,
        runtime_context_service: AgentRuntimeContextService | None = None,
        middleware_factory: MiddlewareFactory | None = None,
        checkpoint_service: AgentCheckpointService | None = None,
    ):
        """初始化 Agent 组装器。

        Args:
            model_service: 模型服务，负责创建 ChatOpenAI 等模型实例。
            tool_service: 工具服务，负责按工具名筛选本次可用工具。
            prompt_service: Prompt 服务，负责渲染系统提示词。
            runtime_context_service: 运行时上下文服务，负责构建 context schema。
            middleware_factory: 中间件工厂，负责返回本次需要装配的中间件。
            checkpoint_service: Checkpointer 服务，负责 LangGraph 状态持久化。
        """
        self.model_service = model_service or AgentModelService()
        self.tool_service = tool_service or AgentToolService()
        self.prompt_service = prompt_service or AgentPromptService()
        self.runtime_context_service = runtime_context_service or AgentRuntimeContextService()
        self.middleware_factory = middleware_factory or MiddlewareFactory()
        self.checkpoint_service = checkpoint_service or AgentCheckpointService()

    async def assemble(
        self,
        request: AgentRunRequest,
        context: AgentRuntimeContext,
    ) -> AgentAssembly:
        """执行完整的 Agent 组装流程。

        Args:
            request: 通用 Agent 运行请求，包含模型参数、工具白名单、提示词等。
            context: Agent 运行上下文，包含 thread_id、inputs 等业务变量。

        Returns:
            AgentAssembly，包含已组装的 agent、model、tools、middlewares 和调试元数据。
        """
        assembly_started_at = time.perf_counter()
        logger.info(
            "Agent assembly started: thread_id=%s model_alias=%s tools=%s structured_output=%s",
            context.thread_id,
            request.runtime_options.model or self.model_service.config.default_chat_alias,
            request.tools,
            request.response_format is not None,
        )

        # 第一步：从请求中直接构建内部装配配置（不再通过中间方法包装）。
        features = AgentFeatureConfig(
            enable_memory=request.optional_features.long_term_memory_enabled,
        )
        build_config = AgentBuildConfig(
            system_prompt=request.system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT,
            response_format=request.response_format,
            tool_names=request.tools,
            a2a=request.a2a,
            features=features,
        )
        logger.info(
            "Agent build config ready: thread_id=%s memory=%s",
            context.thread_id,
            features.enable_memory,
        )

        # 第二步：渲染系统提示词。
        system_prompt = self.prompt_service.render_system_prompt(
            build_config.system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT,
            context.inputs,
        )
        logger.info(
            "Agent system prompt rendered: thread_id=%s prompt_length=%d input_keys=%s",
            context.thread_id,
            len(system_prompt),
            sorted(context.inputs.keys()),
        )

        # 第三步：按工具白名单加载本次可用工具。
        tools = self.tool_service.get_tools(build_config.tool_names)
        logger.info(
            "Agent tools loaded: thread_id=%s requested=%d loaded=%d names=%s",
            context.thread_id,
            len(build_config.tool_names),
            len(tools),
            [getattr(tool, "name", tool.__class__.__name__) for tool in tools],
        )

        # 第三步附加：A2A 工具动态注入。仅 a2a.sub_agent_list 非空时装配 a2a_call 工具。
        # 子 Agent 元信息查询和 system prompt 注入由 A2AAgentContextMiddleware 负责。
        if build_config.a2a and build_config.a2a.sub_agent_list:
            from app.server.agent.src.tools.a2a_tool import a2a_call
            tools.append(a2a_call)

        # 第四步：构建 LangChain runtime context schema。
        context_schema = self.runtime_context_service.get_context_schema()

        # 第五步：创建中间件实例，并提取中间件声明的 LangGraph state schema。
        middlewares = self.middleware_factory.build_langchain_middlewares(features)
        middleware_names = self.middleware_factory.describe_middlewares(features)
        state_schema_names = self.middleware_factory.describe_state_schemas(middlewares)
        logger.info(
            "Agent middlewares assembled: thread_id=%s middlewares=%s state_schemas=%s",
            context.thread_id,
            middleware_names,
            state_schema_names,
        )

        # 第六步：创建聊天模型。
        model = self.model_service.create_chat_model(
            model=request.runtime_options.model,
            temperature=request.runtime_options.temperature,
            timeout_seconds=request.runtime_options.timeout_seconds,
            max_retries=request.runtime_options.max_retries,
        )

        # 第七步：获取 LangGraph checkpointer。
        # 普通 Agent 默认使用 PostgreSQL checkpointer，保留模型可见会话状态。
        # A2A 子 Agent 会以 stateless=True 运行，此时不挂 checkpointer，避免子任务状态落入 checkpoint 表。
        if request.runtime_options.stateless:
            checkpointer = None
            logger.info(
                "Agent checkpointer skipped: thread_id=%s stateless=%s",
                context.thread_id,
                request.runtime_options.stateless,
            )
        else:
            checkpointer = await self.checkpoint_service.get_checkpointer()
            logger.info(
                "Agent checkpointer prepared: thread_id=%s enabled=%s",
                context.thread_id,
                checkpointer is not None,
            )

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
        logger.info(
            "Agent assembly completed: thread_id=%s elapsed_ms=%.2f",
            context.thread_id,
            (time.perf_counter() - assembly_started_at) * 1000,
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
                "stateless": request.runtime_options.stateless,
                "structured_output_enabled": build_config.response_format is not None,
            },
        )

