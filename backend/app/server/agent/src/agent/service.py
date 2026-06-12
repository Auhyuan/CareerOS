from app.server.agent.src.agent.assembly import AgentAssembly
from app.server.agent.src.checkpoint import AgentCheckpointService
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
    """平台通用 Agent 服务。

    这个类是 agent 层的核心装配入口，职责类似 agent_engine 里的
    LangChainAgentService.create_agent_platform(...)：

    1. 根据请求构建 Agent 装配配置。
    2. 构建运行时上下文，也就是 sys_var / user_var / metadata。
    3. 渲染系统提示词。
    4. 加载工具。
    5. 加载中间件。
    6. 创建模型。
    7. 调用 LangChain create_agent(...) 完成真正的 agent 组装。
    8. 运行 agent，并在结束后交给记忆服务处理交互结果。
    """

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
    ):
        """
        初始化平台通用 Agent 服务。

        Args:
            model_service: 模型服务，负责 ChatOpenAI、Embedding、后续 Rerank。
            tool_service: 工具服务，负责工具注册、工具筛选、工具注入配置。
            prompt_service: 提示词服务，负责基础 prompt 和模块 prompt 渲染。
            runtime_context_service: 运行上下文服务，负责构建 sys_var、user_var、metadata。
            middleware_factory: 中间件工厂，负责按配置返回中间件列表。
            memory_service: 记忆服务，后续区分短期上下文和长期记忆。
            checkpoint_service: Checkpoint 服务，后续接 LangGraph 状态持久化。
        """
        self.model_service = model_service or AgentModelService()
        self.tool_service = tool_service or AgentToolService()
        self.prompt_service = prompt_service or AgentPromptService()
        self.runtime_context_service = runtime_context_service or AgentRuntimeContextService()
        self.middleware_factory = middleware_factory or MiddlewareFactory()
        self.memory_service = memory_service or AgentMemoryService()
        self.checkpoint_service = checkpoint_service or AgentCheckpointService()

    def build_config_from_request(self, request: AgentRunRequest) -> AgentBuildConfig:
        """
        根据运行请求构建 Agent 装配配置。

        Args:
            request: 通用 Agent 运行请求。

        Returns:
            AgentBuildConfig 装配配置。
        """
        # API 层不直接暴露“中间件开关”，而是暴露 optional_features 这种业务能力参数。
        # 这里把可选业务能力转换成 agent 内部装配配置：
        # - 基础中间件继续默认开启，例如工具异常处理、工具参数注入、工具日志。
        # - 可选能力按请求参数开启，例如长期记忆、延迟工具过滤、checkpoint。
        features = AgentFeatureConfig(
            enable_memory=request.optional_features.long_term_memory_enabled,
            enable_deferred_tool_filter=request.optional_features.deferred_tool_filter_enabled,
            enable_checkpointer=request.optional_features.checkpoint_enabled,
        )

        return AgentBuildConfig(
            agent_name=request.agent_name,
            system_prompt=request.system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT,
            tool_names=request.tools,
            features=features,
        )

    def assemble_agent(self, request: AgentRunRequest, context: AgentRuntimeContext) -> AgentAssembly:
        """
        组装 LangChain Agent。

        Args:
            request: 通用 Agent 运行请求。
            context: Agent 运行上下文。

        Returns:
            AgentAssembly 装配结果。
        """
        # 第一步：把请求转换成“装配配置”。
        # 运行请求里既有用户输入，也有模型参数、工具白名单、系统提示词等内容。
        # 这里抽出真正影响 agent 结构的部分，避免后续 create_agent 时直接依赖 API 请求对象。
        build_config = self.build_config_from_request(request)

        # 第二步：渲染系统提示词。
        # prompt_service 负责把基础 prompt 和业务变量结合起来。
        # 例如后续岗位画像编排层可以传入 {{job_direction}}、{{city}} 等变量。
        system_prompt = self.prompt_service.render_system_prompt(
            build_config.system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT,
            context.inputs,
        )

        # 第三步：根据工具白名单加载工具。
        # 当前工具注册中心还是轻量实现，后续会加入工具参数注入配置、工具分类、
        # 内置工具、业务工具、MCP 工具等能力。
        tools = self.tool_service.get_tools(build_config.tool_names)

        # 第四步：构建 LangChain runtime context schema。
        # 这个 schema 决定中间件里能通过 request.runtime.context 访问哪些字段。
        # 我们参考 agent_engine，预留了 sys_var、user_var、input_messages、memory_enabled 等字段。
        context_schema = self.runtime_context_service.get_context_schema()

        # 第五步：根据能力开关决定中间件列表。
        # describe_middlewares 只返回名字，用于 dry_run 和调试；
        # 真正执行时再 build_langchain_middlewares，避免 dry_run 阶段导入 LangChain 中间件依赖。
        middleware_names = self.middleware_factory.describe_middlewares(build_config.features)

        # dry_run 是架构调试模式。
        # 它只返回“如果真实装配，会装配哪些内容”，不会创建模型，也不会调用 LangChain create_agent。
        # 这样即使本地没配置 MODEL_API_KEY，也能检查 agent 层结构是否正确。
        if request.dry_run:
            return AgentAssembly(
                agent=None,
                model=None,
                tools=tools,
                system_prompt=system_prompt,
                context_schema=context_schema,
                middlewares=[],
                context=context,
                metadata={
                    "dry_run": True,
                    "tool_count": len(tools),
                    "middlewares": middleware_names,
                    "context_schema": context_schema.__name__,
                },
            )

        # 第六步：创建聊天模型。
        # 这里统一走 AgentModelService，底层目前用 ChatOpenAI 适配 OpenAI-compatible 模型。
        # 后续如果不同厂商有特殊参数，也应该在 model 层处理，不要泄露到 agent 组装逻辑里。
        model = self.model_service.create_chat_model(
            model=request.runtime_options.model,
            temperature=request.runtime_options.temperature,
            timeout_seconds=request.runtime_options.timeout_seconds,
            max_retries=request.runtime_options.max_retries,
        )

        # 第七步：创建 LangChain 中间件实例。
        # 中间件会横切模型调用和工具调用，例如工具异常处理、工具日志、工具参数注入、记忆注入等。
        middlewares = self.middleware_factory.build_langchain_middlewares(build_config.features)

        try:
            from langchain.agents import create_agent
        except ImportError as error:
            raise RuntimeError("缺少 LangChain Agent 依赖，请先执行：pip install -r requirements.txt") from error

        # 第八步：真正创建 LangChain agent。
        # 这是整个 agent 层最核心的装配点：
        # model 控制“用哪个模型思考”；
        # tools 控制“能调用哪些外部能力”；
        # system_prompt 控制“角色、目标和约束”；
        # context_schema 控制“运行时上下文结构”；
        # middleware 控制“模型/工具调用链路上的横切能力”。
        agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            context_schema=context_schema,
            middleware=middlewares,
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
                "dry_run": False,
                "tool_count": len(tools),
                "middlewares": middleware_names,
                "context_schema": context_schema.__name__,
            },
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResponse:
        """
        运行通用 Agent。

        Args:
            request: 通用 Agent 运行请求。

        Returns:
            通用 Agent 运行结果。
        """
        # 第一步：先构建运行时上下文。
        # 注意：上下文不是 prompt，它是给 LangChain runtime 和中间件使用的数据结构。
        # 比如工具参数注入中间件后续会从 context.sys_var / context.user_var 里拿参数。
        context = self.runtime_context_service.build_context(request)

        # 第二步：组装 agent。
        # assemble_agent 只负责“把零件装起来”，不负责解释业务结果。
        assembly = self.assemble_agent(request, context)

        # dry_run 直接返回装配信息，方便我们调试平台型 agent 的结构。
        if request.dry_run:
            return AgentRunResponse(
                answer="Agent 装配骨架已就绪，当前为 dry_run，未真实调用模型。",
                metadata={
                    **assembly.metadata,
                    "agent_name": context.agent_name,
                    "thread_id": context.thread_id,
                    "allowed_tools": context.allowed_tools,
                    "system_prompt_preview": assembly.system_prompt[:120],
                },
            )

        # 第三步：真实运行 agent。
        # messages 是 LangChain agent 的标准输入；
        # config.configurable.thread_id 后续用于 checkpointer / LangGraph 状态恢复；
        # context 是传给中间件和 runtime 使用的结构化上下文。
        result = await assembly.agent.ainvoke(
            {"messages": [{"role": "user", "content": request.query}]},
            config={"configurable": {"thread_id": context.thread_id}, "recursion_limit": 50},
            context=context.to_langchain_context(),
        )

        # 第四步：提取最终回答。
        # LangChain agent 的最终结果通常在 messages 的最后一条 AIMessage 中。
        answer = result["messages"][-1].content if result.get("messages") else ""

        # 第五步：把交互交给记忆服务。
        # 当前 MemoryService 还是占位实现，后续可以在这里异步更新长期记忆。
        await self.memory_service.save_interaction(context, answer)

        return AgentRunResponse(
            answer=answer,
            structured_output=result.get("structured_response") or result.get("structured_output"),
            metadata=assembly.metadata,
        )
