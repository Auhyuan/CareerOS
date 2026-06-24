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
from app.server.agent.src.schemas.request import AgentRunRequest
from app.server.agent.src.schemas.response import AgentRunResponse
from app.server.agent.src.tools import AgentToolService


logger = logging.getLogger("capability.agent")


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

        # 向后兼容：API 层通过 agent_service.tool_service 访问工具列表。
        self.tool_service = self.assembler.tool_service

    # ── 运行前置 / 后置（run 与 stream 共用） ──────────────────

    def _prepare_run_context(
        self,
        request: AgentRunRequest,
        db: Session | None,
    ) -> tuple[AgentRuntimeContext, bool]:
        """构建运行上下文并为持久会话写入用户消息。

        这是 run() 和 stream() 的公共前置步骤。
        包含：构建上下文、创建 conversation 记录、写入用户消息。

        Args:
            request: Agent 运行请求。
            db: PostgreSQL Session。

        Returns:
            (运行上下文, 是否启用持久会话记录)。
        """
        context = self.runtime_context_service.build_context(request)
        context_enabled = request.conversation_id is not None and db is not None

        if context_enabled:
            self.context_service.ensure_conversation(
                db,
                conversation_id=context.thread_id,
                metadata={},
            )
            self.context_service.add_user_message(
                db,
                conversation_id=context.thread_id,
                content=request.query,
                metadata={},
            )

        logger.info(
            "Agent run started: thread_id=%s query_length=%d persistent_conversation=%s "
            "structured_output=%s stream=%s",
            context.thread_id,
            len(request.query),
            request.conversation_id is not None,
            request.response_format is not None,
            request.stream,
        )

        return context, context_enabled

    async def _finalize_run(
        self,
        context: AgentRuntimeContext,
        answer: str,
        context_enabled: bool,
        db: Session | None,
    ) -> None:
        """保存长期记忆并为持久会话写入助手回复。

        这是 run() 和 stream() 的公共后置步骤。

        Args:
            context: Agent 运行上下文。
            answer: Agent 最终文本回答。
            context_enabled: 是否启用持久会话记录。
            db: PostgreSQL Session。
        """
        await self.memory_service.save_interaction(context, answer)

        if context_enabled:
            self.context_service.add_assistant_message(
                db,
                conversation_id=context.thread_id,
                content=answer,
                metadata={},
            )

    # ── 同步执行 ────────────────────────────────────────────────

    async def run(self, request: AgentRunRequest, db: Session | None = None) -> AgentRunResponse:
        """运行通用 Agent（非流式）。

        Args:
            request: 通用 Agent 运行请求。
            db: PostgreSQL Session。API 调用场景会传入，非 Web 场景可以为空。

        Returns:
            AgentRunResponse，包含最终回答和结构化输出。
        """
        run_started_at = time.perf_counter()

        # 第一步：构建上下文并准备持久会话。
        context, context_enabled = self._prepare_run_context(request, db)

        # 第二步：组装 Agent。
        try:
            assembly = await self.assembler.assemble(request, context)
        except Exception:
            logger.exception(
                "Agent assembly failed: thread_id=%s elapsed_ms=%.2f",
                context.thread_id,
                (time.perf_counter() - run_started_at) * 1000,
            )
            raise

        # 第三步：真实调用 Agent。
        input_messages = [
            {"role": "user", "content": request.query},
        ]
        logger.info("Agent execution started: thread_id=%s", context.thread_id)
        try:
            result = await assembly.agent.ainvoke(
                {"messages": input_messages},
                config={"configurable": {"thread_id": context.thread_id}, "recursion_limit": 50},
                context=context.to_langchain_context(),
            )
        except Exception as error:
            logger.exception(
                "Agent execution failed: thread_id=%s elapsed_ms=%.2f",
                context.thread_id,
                (time.perf_counter() - run_started_at) * 1000,
            )
            if context_enabled:
                self.context_service.add_error(
                    db,
                    conversation_id=context.thread_id,
                    error_message=f"模型服务出错：{error}",
                )
            raise

        # 第四步：提取最终回答。
        answer = result["messages"][-1].content if result.get("messages") else ""
        structured_output = result.get("structured_response") or result.get("structured_output")

        # AIMessage.tool_calls 记录模型实际发出的工具调用。
        # 统计该值可以区分"工具已装配但模型未选择调用"和"工具执行阶段发生异常"。
        tool_call_names: list[str] = []
        for message in result.get("messages") or []:
            for tool_call in getattr(message, "tool_calls", None) or []:
                tool_name = tool_call.get("name")
                if tool_name:
                    tool_call_names.append(str(tool_name))
        logger.info(
            "Agent execution completed: thread_id=%s answer_length=%d structured_output=%s "
            "tool_call_count=%d tool_calls=%s elapsed_ms=%.2f",
            context.thread_id,
            len(answer) if isinstance(answer, str) else 0,
            structured_output is not None,
            len(tool_call_names),
            tool_call_names,
            (time.perf_counter() - run_started_at) * 1000,
        )

        # 第五步：保存记忆和会话记录。
        await self._finalize_run(context, answer, context_enabled, db)

        logger.info(
            "Agent run finished: thread_id=%s context_saved=%s total_elapsed_ms=%.2f",
            context.thread_id,
            context_enabled,
            (time.perf_counter() - run_started_at) * 1000,
        )

        return AgentRunResponse(
            answer=answer,
            structured_output=structured_output,
        )

    # ── 流式执行 ────────────────────────────────────────────────

    async def stream(self, request: AgentRunRequest, db: Session | None = None) -> AsyncIterator[dict[str, Any]]:
        """流式运行通用 Agent，并产出可转换为 SSE 的事件。

        Args:
            request: 通用 Agent 运行请求；stream=true 时由 API 层调用本方法。
            db: PostgreSQL Session，用于在 conversation_id 非空时写入用户可见会话记录。

        Yields:
            标准化事件字典，包含 type、data 等字段；API 层负责序列化为 SSE。
        """
        run_started_at = time.perf_counter()

        # 第一步：构建上下文并准备持久会话。
        context, context_enabled = self._prepare_run_context(request, db)
        yield {
            "type": "run_start",
            "data": {
                "thread_id": context.thread_id,
                "persistent_conversation": request.conversation_id is not None,
                "stream": True,
            },
        }

        try:
            # 第二步：组装 Agent。
            assembly = await self.assembler.assemble(request, context)
            yield {
                "type": "agent_assembled",
                "data": assembly.metadata,
            }

            # 第三步：只传入本轮用户消息；跨轮历史由 checkpointer 根据 thread_id 恢复。
            input_messages = [{"role": "user", "content": request.query}]
            invoke_config = {"configurable": {"thread_id": context.thread_id}, "recursion_limit": 50}
            final_result: dict[str, Any] | None = None

            # 第四步：消费 LangChain/LangGraph 事件流，并转换成平台统一事件。
            async for raw_event in assembly.agent.astream_events(
                {"messages": input_messages},
                config=invoke_config,
                context=context.to_langchain_context(),
                version="v2",
            ):
                normalized_event = self._normalize_stream_event(raw_event)
                if normalized_event is not None:
                    yield normalized_event

                output = self._extract_stream_output(raw_event)
                if output is not None:
                    final_result = output

            # 第五步：提取最终回答和结构化输出。
            answer = self._extract_answer_from_result(final_result or {})
            structured_output = self._extract_structured_output_from_result(final_result or {})
            await self._finalize_run(context, answer, context_enabled, db)

            yield {
                "type": "final",
                "data": {
                    "answer": answer,
                    "structured_output": structured_output,
                },
            }
            yield {
                "type": "run_end",
                "data": {
                    "thread_id": context.thread_id,
                    "elapsed_ms": (time.perf_counter() - run_started_at) * 1000,
                },
            }
        except Exception as error:
            logger.exception(
                "Agent stream execution failed: thread_id=%s elapsed_ms=%.2f",
                context.thread_id,
                (time.perf_counter() - run_started_at) * 1000,
            )
            if context_enabled:
                self.context_service.add_error(
                    db,
                    conversation_id=context.thread_id,
                    error_message=f"模型服务出错：{error}",
                )
            yield {
                "type": "error",
                "data": {
                    "message": str(error),
                    "error_type": error.__class__.__name__,
                },
            }

    # ── 流事件解析 ──────────────────────────────────────────────

    def _normalize_stream_event(self, raw_event: dict[str, Any]) -> dict[str, Any] | None:
        """将 LangChain 原始流事件转换为平台 SSE 事件。

        Args:
            raw_event: LangChain/LangGraph astream_events 产出的原始事件。

        Returns:
            可序列化的平台事件；无法映射或不需要暴露时返回 None。
        """
        event_name = raw_event.get("event")
        runnable_name = raw_event.get("name")
        data = raw_event.get("data") or {}

        if event_name == "on_chat_model_start":
            return {"type": "model_start", "data": {"name": runnable_name}}

        if event_name == "on_chat_model_stream":
            chunk = data.get("chunk")
            reasoning = self._extract_reasoning_text(chunk)
            content = self._extract_message_text(chunk)
            if reasoning:
                return {"type": "reasoning_delta", "data": {"content": reasoning}}
            if content:
                return {"type": "model_delta", "data": {"content": content}}
            return None

        if event_name == "on_chat_model_end":
            return {"type": "model_end", "data": {"name": runnable_name}}

        if event_name == "on_tool_start":
            return {
                "type": "tool_call_start",
                "data": {
                    "tool_name": runnable_name,
                    "input": data.get("input"),
                },
            }

        if event_name == "on_tool_end":
            return {
                "type": "tool_call_result",
                "data": {
                    "tool_name": runnable_name,
                    "output": data.get("output"),
                },
            }

        return None

    def _extract_stream_output(self, raw_event: dict[str, Any]) -> dict[str, Any] | None:
        """从原始流事件中提取可能的最终 Agent 输出。

        Args:
            raw_event: LangChain/LangGraph astream_events 产出的原始事件。

        Returns:
            包含 messages 或 structured_response 的输出字典；没有时返回 None。
        """
        if raw_event.get("event") != "on_chain_end":
            return None

        output = (raw_event.get("data") or {}).get("output")
        if isinstance(output, dict) and (
            "messages" in output
            or "structured_response" in output
            or "structured_output" in output
        ):
            return output
        return None

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
        content = getattr(messages[-1], "content", "")
        return content if isinstance(content, str) else str(content)

    def _extract_structured_output_from_result(self, result: dict[str, Any]) -> dict[str, Any] | None:
        """从 Agent 最终结果中提取结构化输出。

        Args:
            result: Agent 执行最终结果。

        Returns:
            结构化输出字典；不存在时返回 None。
        """
        structured_output = result.get("structured_response") or result.get("structured_output")
        return structured_output if isinstance(structured_output, dict) else None

    def _extract_message_text(self, message: Any) -> str:
        """从模型消息或消息分片中提取普通文本。

        Args:
            message: LangChain 消息对象、消息分片或原生字符串。

        Returns:
            提取出的文本；没有文本时返回空字符串。
        """
        if message is None:
            return ""
        if isinstance(message, str):
            return message

        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                    parts.append(str(item.get("text") or item.get("content") or ""))
            return "".join(parts)
        return ""

    def _extract_reasoning_text(self, message: Any) -> str:
        """从模型消息分片中提取供应商返回的思考内容。

        Args:
            message: LangChain 消息对象或消息分片。

        Returns:
            模型供应商显式返回的 reasoning 文本；不支持时返回空字符串。
        """
        if message is None:
            return ""

        additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
        for key in ("reasoning_content", "reasoning", "reasoning_text"):
            value = additional_kwargs.get(key)
            if isinstance(value, str) and value:
                return value

        response_metadata = getattr(message, "response_metadata", {}) or {}
        for key in ("reasoning_content", "reasoning", "reasoning_text"):
            value = response_metadata.get(key)
            if isinstance(value, str) and value:
                return value

        content = getattr(message, "content", None)
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"reasoning", "thinking"}:
                    parts.append(str(item.get("text") or item.get("content") or ""))
            return "".join(parts)
        return ""
