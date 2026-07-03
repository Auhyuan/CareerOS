import logging
import time
from typing import Any, AsyncIterator

from sqlmodel import Session

from app.server.agent.src.agent.assembler import AgentAssembler
from app.server.agent.src.checkpoint import AgentCheckpointService
from app.server.agent.src.context import AgentContextService
from app.server.agent.src.memory import AgentMemoryService
from app.server.agent.src.middlewares import MiddlewareFactory
from app.server.agent.src.model import AgentModelService
from app.server.agent.src.prompts import AgentPromptService
from app.server.agent.src.runtime import AgentRuntimeContext, AgentRuntimeContextService
from app.server.agent.src.runs import AgentRunService
from app.server.agent.src.schemas.request import AgentRunRequest, ModelRuntimeOptions
from app.server.agent.src.schemas.response import AgentRunResponse
from app.server.agent.src.templates.schemas import AgentTemplateConfig
from app.server.agent.src.templates.service import AgentTemplateService
from app.server.agent.src.tools import AgentToolService
from app.server.agent.src.agent.streaming import AgentStreamEventParser


logger = logging.getLogger("ai_backend.agent")


class AgentService:
    """平台通用 Agent 服务，负责运行上下文管理、会话持久化和执行调度。

    Agent 组装流程已提取到 AgentAssembler，本层只关心：
    - 运行上下文构建（_prepare_run_context）
    - 调度 AgentAssembler 完成组装
    - 同步 / 流式执行
    - 运行后收尾（_finalize_run）
    """

    def __init__(
        self,
        *,
        assembler: AgentAssembler | None = None,
        model_service: AgentModelService | None = None,
        tool_service: AgentToolService | None = None,
        prompt_service: AgentPromptService | None = None,
        runtime_context_service: AgentRuntimeContextService | None = None,
        middleware_factory: MiddlewareFactory | None = None,
        memory_service: AgentMemoryService | None = None,
        checkpoint_service: AgentCheckpointService | None = None,
        context_service: AgentContextService | None = None,
        run_service: AgentRunService | None = None,
        template_service: AgentTemplateService | None = None,
        stream_parser: AgentStreamEventParser | None = None,
    ):
        """初始化平台通用 Agent 服务。

        Args:
            assembler: Agent 组装器，不传时自动创建。
            model_service: 模型服务（仅在未传 assembler 时用于构建默认组装器）。
            tool_service: 工具服务（同上）。
            prompt_service: Prompt 服务（同上）。
            runtime_context_service: 运行时上下文服务，负责构建 thread_id、inputs 等。
            middleware_factory: 中间件工厂（同上）。
            memory_service: 记忆服务，当前先预留长期记忆能力。
            checkpoint_service: Checkpointer 服务（同上）。
            context_service: 历史会话服务，负责读写 agent_conversations 和 agent_messages。
            run_service: Agent 主运行记录服务，负责读写 agent_runs。
            template_service: Agent 模板服务，负责按 agent_id 加载模板配置。
            stream_parser: 流式消息解析器，负责把 LangGraph messages 分片转成 SSE 事件。
        """
        self.assembler = assembler or AgentAssembler(
            model_service=model_service or AgentModelService(),
            tool_service=tool_service or AgentToolService(),
            prompt_service=prompt_service or AgentPromptService(),
            runtime_context_service=runtime_context_service or AgentRuntimeContextService(),
            middleware_factory=middleware_factory or MiddlewareFactory(),
            checkpoint_service=checkpoint_service or AgentCheckpointService(),
        )
        self.runtime_context_service = runtime_context_service or AgentRuntimeContextService()
        self.memory_service = memory_service or AgentMemoryService()
        self.context_service = context_service or AgentContextService()
        self.run_service = run_service or AgentRunService()
        self.template_service = template_service or AgentTemplateService()
        self.stream_parser = stream_parser or AgentStreamEventParser()

        # 向后兼容：API 层通过 agent_service.tool_service 访问工具列表。
        self.tool_service = self.assembler.tool_service

    # ── 运行前置 / 后置（run 与 stream 共用） ──────────────────

    def _build_conversation_title(self, query: str) -> str:
        """根据用户第一条问题生成会话标题。

        Args:
            query: 用户本轮输入文本。

        Returns:
            清理空白并截断到数据库 title 字段长度以内的标题；输入为空时返回“新会话”。
        """
        # 会话标题用于前端展示，不参与 Agent 推理；这里只做轻量清洗，避免过度加工用户原话。
        title = " ".join((query or "").split())
        if not title:
            return "新会话"
        return title[:255]

    def _resolve_template_request(self, request: AgentRunRequest, db: Session | None) -> AgentRunRequest:
        """根据 agent_id 加载模板配置，并按“模板优先”规则合并本次请求。

        Args:
            request: API 或内部调用传入的原始运行请求。
            db: PostgreSQL Session；API 调用场景会传入，A2A 等内部场景可能为空。

        Returns:
            合并模板后的 AgentRunRequest；未传 agent_id 时原样返回。
        """
        if not request.agent_id:
            return request

        template_config = self._load_template_config(request.agent_id, db)
        update_data = {
            # 传入 agent_id 后，模板中的核心装配配置拥有最高优先级。
            # 请求体里的 system_prompt=""、tools=[] 只表示前端表单默认值，不能覆盖模板。
            "system_prompt": template_config.system_prompt or request.system_prompt,
            "tools": list(template_config.tools or request.tools or []),
            "optional_features": template_config.optional_features or request.optional_features,
            "a2a": template_config.a2a if template_config.a2a is not None else request.a2a,
            "runtime_options": self._resolve_template_runtime_options(
                template_config.runtime_options,
                request.runtime_options,
            ),
        }
        return request.model_copy(update=update_data, deep=True)

    def _load_template_config(self, agent_id: str, db: Session | None) -> AgentTemplateConfig:
        """按 agent_id 查询启用中的 Agent 模板配置。

        Args:
            agent_id: Agent 模板 ID。
            db: PostgreSQL Session；为空时临时打开只读会话。

        Returns:
            AgentTemplateConfig 模板配置。
        """
        if db is not None:
            template = self.template_service.get_template(db, agent_id)
        else:
            from app.common.db.postgres_db import get_db_session

            with get_db_session() as inner_db:
                template = self.template_service.get_template(inner_db, agent_id)

        if template is None:
            raise RuntimeError(f"Agent 模板不存在: {agent_id}")
        if template.status != "active":
            raise RuntimeError(f"Agent 模板未启用: {agent_id}")
        return template.config

    def _resolve_template_runtime_options(
        self,
        template_options: ModelRuntimeOptions,
        request_options: ModelRuntimeOptions,
    ) -> ModelRuntimeOptions:
        """按“模板优先”规则确定模型运行参数。

        Args:
            template_options: 模板默认模型运行参数。
            request_options: 本次请求传入的模型运行参数。

        Returns:
            合并后的模型运行参数；模板缺少 model_code 时才使用请求体兜底。
        """
        # 模型选择属于 Agent 模板的核心能力配置，不能被请求体中的空值或临时字段覆盖。
        # 只有模板没有绑定模型时，才允许使用请求体里的 model_code 作为兜底，便于临时模板测试。
        merged = template_options.model_dump(mode="python")
        if not merged.get("model_code") and request_options.model_code:
            merged["model_code"] = request_options.model_code
        return ModelRuntimeOptions(**merged)

    def _prepare_run_context(
        self,
        request: AgentRunRequest,
        db: Session | None,
    ) -> tuple[AgentRuntimeContext, bool, bool]:
        """构建运行上下文，并写入用户消息和主运行记录。

        这是 run() 和 stream() 的公共前置步骤。
        普通 API 调用会传入 db，因此会记录 agent_runs；A2A 子 Agent 调用会传 db=None，
        子 Agent 的运行记录由 a2a_call 工具提前写入 agent_runs(run_type=sub)。

        Args:
            request: Agent 运行请求。
            db: PostgreSQL Session。

        Returns:
            (运行上下文, 是否启用持久会话记录, 是否写入主运行记录)。
        """
        context = self.runtime_context_service.build_context(request)
        context_enabled = request.conversation_id is not None and db is not None
        run_record_enabled = db is not None
        user_message_id: str | None = None

        if context_enabled:
            self.context_service.ensure_conversation(
                db,
                conversation_id=context.thread_id,
                title=self._build_conversation_title(request.query),
                metadata={},
            )
            user_message = self.context_service.add_user_message(
                db,
                conversation_id=context.thread_id,
                content=request.query,
                metadata={"run_id": context.run_id},
            )
            user_message_id = user_message.message_id

        if run_record_enabled:
            self.run_service.create_running(
                db,
                run_id=context.run_id,
                run_type="main",
                conversation_id=context.thread_id if request.conversation_id else None,
                user_message_id=user_message_id,
                query=request.query,
                agent_id=request.agent_id,
                metadata={
                    "agent_id": request.agent_id,
                    "model_code": request.runtime_options.model_code,
                    "tools": request.tools,
                    "a2a_sub_agent_list": request.a2a.sub_agent_list if request.a2a else [],
                },
            )
        logger.info(
            "Agent 运行开始: run_id=%s thread_id=%s query_length=%d persistent_conversation=%s "
            "stream=%s conversation_id_present=%s",
            context.run_id,
            context.thread_id,
            len(request.query),
            request.conversation_id is not None,
            request.stream,
            request.conversation_id is not None,
        )

        return context, context_enabled, run_record_enabled

    async def _finalize_run(
        self,
        context: AgentRuntimeContext,
        answer: str,
        context_enabled: bool,
        run_record_enabled: bool,
        db: Session | None,
        elapsed_ms: float,
    ) -> None:
        """保存长期记忆、助手消息，并把主运行记录标记为成功。

        Args:
            context: Agent 运行上下文。
            answer: Agent 最终文本回答。
            context_enabled: 是否启用持久会话记录。
            run_record_enabled: 是否启用主运行记录。
            db: PostgreSQL Session。
            elapsed_ms: 本次运行总耗时，单位毫秒。
        """
        await self.memory_service.save_interaction(context, answer)

        assistant_message_id: str | None = None
        if context_enabled:
            assistant_message = self.context_service.add_assistant_message(
                db,
                conversation_id=context.thread_id,
                content=answer,
                metadata={"run_id": context.run_id},
            )
            assistant_message_id = assistant_message.message_id

        if run_record_enabled and db is not None:
            self.run_service.mark_success(
                db,
                run_id=context.run_id,
                answer=answer,
                assistant_message_id=assistant_message_id,
                elapsed_ms=elapsed_ms,
            )

    def _mark_run_failed(
        self,
        context: AgentRuntimeContext,
        run_record_enabled: bool,
        db: Session | None,
        error: Exception,
        elapsed_ms: float,
    ) -> None:
        """把主运行记录标记为失败。

        Args:
            context: Agent 运行上下文。
            run_record_enabled: 是否启用主运行记录。
            db: PostgreSQL Session。
            error: 运行过程中捕获到的异常。
            elapsed_ms: 失败前耗时，单位毫秒。
        """
        if run_record_enabled and db is not None:
            self.run_service.mark_failed(
                db,
                run_id=context.run_id,
                error_message=str(error),
                elapsed_ms=elapsed_ms,
            )

    # ── 同步执行 ────────────────────────────────────────────────

    async def run(self, request: AgentRunRequest, db: Session | None = None) -> AgentRunResponse:
        """运行通用 Agent（非流式）。

        Args:
            request: 通用 Agent 运行请求。
            db: PostgreSQL Session。API 调用场景会传入；A2A 子 Agent 会传 None，避免写入主运行表。

        Returns:
            AgentRunResponse，包含本次 run_id、最终回答和结构化输出。
        """
        run_started_at = time.perf_counter()

        # 第一步：如果传入 agent_id，先加载模板并合并本次运行覆盖配置。
        request = self._resolve_template_request(request, db)

        # 第二步：构建上下文、写入用户消息，并创建 agent_runs 主运行记录。
        context, context_enabled, run_record_enabled = self._prepare_run_context(request, db)

        try:
            # 第三步：组装 Agent。这里会加载模型、工具、中间件和 checkpointer。
            assembly = await self.assembler.assemble(request, context, db)
        except Exception as error:
            elapsed_ms = (time.perf_counter() - run_started_at) * 1000
            logger.exception(
                "Agent 组装失败: run_id=%s thread_id=%s elapsed_ms=%.2f",
                context.run_id,
                context.thread_id,
                elapsed_ms,
            )
            self._mark_run_failed(context, run_record_enabled, db, error, elapsed_ms)
            raise

        # 第三步：只传入本轮用户消息；跨轮 Agent 记忆由 checkpointer 根据 thread_id 恢复。
        input_messages = [{"role": "user", "content": request.query}]
        logger.info("Agent 执行开始: run_id=%s thread_id=%s", context.run_id, context.thread_id)
        try:
            result = await assembly.agent.ainvoke(
                {"messages": input_messages},
                config={"configurable": {"thread_id": context.thread_id}, "recursion_limit": 50},
                context=context.to_langchain_context(),
            )
        except Exception as error:
            elapsed_ms = (time.perf_counter() - run_started_at) * 1000
            logger.exception(
                "Agent 执行失败: run_id=%s thread_id=%s elapsed_ms=%.2f",
                context.run_id,
                context.thread_id,
                elapsed_ms,
            )
            self._mark_run_failed(context, run_record_enabled, db, error, elapsed_ms)
            if context_enabled:
                self.context_service.add_error(
                    db,
                    conversation_id=context.thread_id,
                    error_message=f"模型服务出错：{error}",
                    metadata={"run_id": context.run_id},
                )
            raise

        # 第四步：提取最终回答和结构化输出。
        answer = result["messages"][-1].content if result.get("messages") else ""

        # AIMessage.tool_calls 记录模型实际发出的工具调用。
        # 统计该值可以区分“工具已装配但模型未选择调用”和“工具执行阶段发生异常”。
        tool_call_names: list[str] = []
        for message in result.get("messages") or []:
            for tool_call in getattr(message, "tool_calls", None) or []:
                tool_name = tool_call.get("name")
                if tool_name:
                    tool_call_names.append(str(tool_name))

        elapsed_ms = (time.perf_counter() - run_started_at) * 1000
        logger.info(
            "Agent 执行完成: run_id=%s thread_id=%s answer_length=%d "
            "tool_call_count=%d tool_calls=%s elapsed_ms=%.2f",
            context.run_id,
            context.thread_id,
            len(answer) if isinstance(answer, str) else 0,
            len(tool_call_names),
            tool_call_names,
            elapsed_ms,
        )

        # 第五步：保存记忆、写入助手消息，并把 agent_runs 标记为 success。
        await self._finalize_run(
            context,
            answer,
            context_enabled,
            run_record_enabled,
            db,
            elapsed_ms,
        )

        logger.info(
            "Agent 运行结束: run_id=%s thread_id=%s context_saved=%s total_elapsed_ms=%.2f",
            context.run_id,
            context.thread_id,
            context_enabled,
            elapsed_ms,
        )

        return AgentRunResponse(
            run_id=context.run_id,
            answer=answer,
        )

    # ── 流式执行 ────────────────────────────────────────────────
    async def stream(self, request: AgentRunRequest, db: Session | None = None) -> AsyncIterator[dict[str, Any]]:
        """流式运行通用 Agent，并产出可转换为 SSE 的事件。

        Args:
            request: 通用 Agent 运行请求；stream=true 时由 API 层调用本方法。
            db: PostgreSQL Session，用于写入 agent_runs 和用户可见会话记录。

        Yields:
            标准化事件字典，包含 type、data 等字段；API 层负责序列化为 SSE。
        """
        run_started_at = time.perf_counter()

        # 第一步：如果传入 agent_id，先加载模板并合并本次运行覆盖配置。
        request = self._resolve_template_request(request, db)

        # 第二步：构建上下文、写入用户消息，并创建 agent_runs 主运行记录。
        context, context_enabled, run_record_enabled = self._prepare_run_context(request, db)
        yield {
            "type": "run_start",
            "data": {
                "run_id": context.run_id,
                "thread_id": context.thread_id,
                "persistent_conversation": request.conversation_id is not None,
                "stream": True,
            },
        }

        try:
            # 第三步：组装 Agent。这里会加载模型、工具、中间件和 checkpointer。
            assembly = await self.assembler.assemble(request, context, db)
            yield {
                "type": "agent_assembled",
                "data": {
                    "run_id": context.run_id,
                    **assembly.metadata,
                },
            }

            # 第三步：只传入本轮用户消息；跨轮 Agent 记忆由 checkpointer 根据 thread_id 恢复。
            input_messages = [{"role": "user", "content": request.query}]
            invoke_config = {"configurable": {"thread_id": context.thread_id}, "recursion_limit": 50}
            answer_parts: list[str] = []

            # 第四步：同时消费 messages 和 updates 流。
            # - messages：模型 token、reasoning、工具调用等前端实时内容。
            # - updates：LangGraph interrupt 只会在 updates 中出现，单独使用 messages 会丢失中断事件。
            # 流式模式下前端已经实时收到了 model_delta，因此接口末尾不再额外发送 final 事件；
            # 这里仅在后端累计正文 token，用于写入 agent_messages / agent_runs。
            interrupted_payload: dict[str, Any] | None = None
            async for stream_chunk in assembly.agent.astream(
                {"messages": input_messages},
                config=invoke_config,
                context=context.to_langchain_context(),
                stream_mode=["messages", "updates"],
            ):
                stream_mode, chunk = stream_chunk if isinstance(stream_chunk, tuple) and len(stream_chunk) == 2 else ("messages", stream_chunk)

                if stream_mode == "messages":
                    for normalized_event in self.stream_parser.normalize_message_stream_chunk(chunk):
                        if normalized_event.get("type") == "model_delta":
                            content = (normalized_event.get("data") or {}).get("content")
                            if isinstance(content, str) and content:
                                answer_parts.append(content)
                        yield normalized_event
                    continue

                if stream_mode == "updates":
                    interrupt_event = self._extract_interrupt_event(chunk, context.run_id, context.thread_id)
                    if interrupt_event is not None:
                        interrupted_payload = (interrupt_event.get("data") or {}).get("payload")
                        yield interrupt_event

            elapsed_ms = (time.perf_counter() - run_started_at) * 1000
            if interrupted_payload is not None:
                interrupt_type = str(interrupted_payload.get("type") or "unknown") if isinstance(interrupted_payload, dict) else "unknown"
                if run_record_enabled and db is not None:
                    self.run_service.mark_interrupted(
                        db,
                        run_id=context.run_id,
                        interrupt_type=interrupt_type,
                        interrupt_payload=interrupted_payload,
                        elapsed_ms=elapsed_ms,
                    )
                yield {
                    "type": "run_end",
                    "data": {
                        "run_id": context.run_id,
                        "thread_id": context.thread_id,
                        "status": "interrupted",
                        "interrupt_type": interrupt_type,
                        "elapsed_ms": elapsed_ms,
                        "answer_length": len("".join(answer_parts)),
                    },
                }
                return

            # 第五步：流式 token 已经全部推送完成，使用累计正文作为最终回答。
            # 这里不能调用 aget_state()，因为无状态运行不会挂 checkpointer，调用会触发 No checkpointer set。
            answer = "".join(answer_parts)
            await self._finalize_run(
                context,
                answer,
                context_enabled,
                run_record_enabled,
                db,
                elapsed_ms,
            )

            yield {
                "type": "run_end",
                "data": {
                    "run_id": context.run_id,
                    "thread_id": context.thread_id,
                    "status": "success",
                    "elapsed_ms": elapsed_ms,
                    "answer_length": len(answer),
                },
            }
        except Exception as error:
            elapsed_ms = (time.perf_counter() - run_started_at) * 1000
            logger.exception(
                "Agent 流式执行失败: run_id=%s thread_id=%s elapsed_ms=%.2f",
                context.run_id,
                context.thread_id,
                elapsed_ms,
            )
            self._mark_run_failed(context, run_record_enabled, db, error, elapsed_ms)
            if context_enabled:
                self.context_service.add_error(
                    db,
                    conversation_id=context.thread_id,
                    error_message=f"模型服务出错：{error}",
                    metadata={"run_id": context.run_id},
                )
            yield {
                "type": "error",
                "data": {
                    "run_id": context.run_id,
                    "message": str(error),
                    "error_type": error.__class__.__name__,
                },
            }

    def _extract_interrupt_event(
        self,
        chunk: Any,
        run_id: str,
        thread_id: str,
    ) -> dict[str, Any] | None:
        """从 LangGraph updates 分片中提取 interrupt 事件。

        Args:
            chunk: LangGraph updates 模式返回的分片。
            run_id: 当前 Agent 运行 ID。
            thread_id: 当前 LangGraph thread ID。

        Returns:
            可直接返回给前端的 interrupt 事件；没有中断时返回 None。
        """
        if not isinstance(chunk, dict):
            return None
        interrupts = chunk.get("__interrupt__")
        if not interrupts:
            return None

        first_interrupt = interrupts[0] if isinstance(interrupts, (list, tuple)) else interrupts
        if isinstance(first_interrupt, dict) and "value" in first_interrupt:
            payload = first_interrupt.get("value")
        else:
            payload = getattr(first_interrupt, "value", first_interrupt)
        safe_payload = self.stream_parser.safe_event_value(payload)
        if not isinstance(safe_payload, dict):
            safe_payload = {"type": "unknown", "data": {"value": safe_payload}}

        return {
            "type": "interrupt",
            "data": {
                "run_id": run_id,
                "thread_id": thread_id,
                "payload": safe_payload,
            },
        }

    # ── 结果提取 ────────────────────────────────────────────────

    def _extract_answer_from_result(self, result: dict[str, Any]) -> str:
        """从 Agent 最终结果中提取最终文本回答。

        Args:
            result: Agent 执行最终结果。

        Returns:
            最终回答文本；不存在时返回空字符串。
        """
        messages = result.get("messages") or []
        if not messages:
            return ""

        last_message = messages[-1]
        # final_result.values 经过 safe_event_value 后，LangChain 消息对象会变成 dict；
        # 非流式路径里仍可能是原始消息对象，所以这里两种形态都要兼容。
        if isinstance(last_message, dict):
            content = last_message.get("content", "")
        else:
            content = getattr(last_message, "content", "")

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # 兼容多模态 / reasoning block 形态，只抽取可展示文本。
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                    parts.append(str(item.get("text") or item.get("content") or ""))
            return "".join(parts)
        return str(content) if content is not None else ""
