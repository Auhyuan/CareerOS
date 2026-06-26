"""A2A 工具：把子 Agent 调用包装成 LangChain Tool。"""

import logging
import time
from typing import Any
from uuid import uuid4

from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class A2ACallInput(BaseModel):
    """A2A 工具调用参数。"""

    agent_id: str = Field(description="要调用的子 Agent ID")
    query: str = Field(description="传给子 Agent 的任务指令")


def _get_runtime_context(runtime: ToolRuntime | None) -> dict[str, Any]:
    """从 LangGraph ToolRuntime 中提取运行时上下文。

    Args:
        runtime: LangGraph 在工具调用时注入的运行时对象。

    Returns:
        runtime.context 对应的字典。没有 context 时返回空字典。
    """
    if runtime is None:
        return {}

    context = getattr(runtime, "context", None)
    if context is None:
        return {}
    if isinstance(context, dict):
        return context
    if hasattr(context, "model_dump"):
        return context.model_dump()

    # 兼容少数可迭代 context 对象；如果不能安全转换，就返回空字典。
    return dict(context) if hasattr(context, "__iter__") else {}


def _mark_agent_run_success(run_id: str, output_text: str, elapsed_ms: float) -> None:
    """把 A2A 子 Agent 运行记录标记为成功。

    Args:
        run_id: 子 Agent 本次运行 ID。
        output_text: 子 Agent 最终输出文本。
        elapsed_ms: 子 Agent 调用耗时，单位毫秒。
    """
    from app.common.db.postgres_db import get_db_session
    from app.server.agent.src.runs import AgentRunService

    with get_db_session() as db:
        AgentRunService().mark_success(db, run_id=run_id, answer=output_text, elapsed_ms=elapsed_ms)


def _mark_agent_run_failed(run_id: str, error_message: str, elapsed_ms: float) -> None:
    """把 A2A 子 Agent 运行记录标记为失败。

    Args:
        run_id: 子 Agent 本次运行 ID。
        error_message: 子 Agent 调用失败原因。
        elapsed_ms: 子 Agent 调用失败前耗时，单位毫秒。
    """
    from app.common.db.postgres_db import get_db_session
    from app.server.agent.src.runs import AgentRunService

    with get_db_session() as db:
        AgentRunService().mark_failed(db, run_id=run_id, error_message=error_message, elapsed_ms=elapsed_ms)


@tool("a2a_call", args_schema=A2ACallInput)
async def a2a_call(agent_id: str, query: str, runtime: ToolRuntime | None = None) -> str:
    """调用子 Agent 执行子任务。

    这个工具只负责“主 Agent 调用子 Agent”的第一版闭环，不做流式转发。
    子 Agent 返回完整文本后，主 Agent 再把结果整合进最终回答。

    安全边界：
    1. agent_id 必须在本次运行允许的 a2a_sub_agent_list 中。
    2. 目标 Agent 模板必须声明 is_sub_agent=true。
    3. 子 Agent 调用时不传 conversation_id，因此不落 LangGraph checkpoint。
    4. 子 Agent 调用时 long_term_memory_enabled=False，避免读写用户长期记忆。
    5. 子 Agent 调用时 a2a=None，避免第一版出现递归式 Agent 调 Agent。

    Args:
        agent_id: 要调用的子 Agent 模板 ID。
        query: 传给子 Agent 的完整任务说明。
        runtime: LangGraph 注入的工具运行时对象，模型不会看到这个参数。

    Returns:
        子 Agent 的最终文本回答；校验失败或调用失败时返回错误说明文本。
    """
    from app.common.db.postgres_db import get_db_session
    from app.server.agent.src.agent.service import AgentService
    from app.server.agent.src.runs import AgentRunService
    from app.server.agent.src.schemas.request import AgentOptionalFeatures, AgentRunRequest
    from app.server.agent.src.templates.service import AgentTemplateService

    # 第一层校验：只能调用本次 runtime context 白名单中的子 Agent。
    # 这个白名单来自 /agent/run 的 a2a.sub_agent_list，而不是模型自己决定。
    runtime_context = _get_runtime_context(runtime)
    allowed_agent_ids = set(runtime_context.get("a2a_sub_agent_list") or [])
    if not allowed_agent_ids:
        return "错误：当前 Agent 未配置可调用的子 Agent，不能执行 A2A 调用。"
    if agent_id not in allowed_agent_ids:
        return f"错误：子 Agent {agent_id} 不在本次允许调用的 A2A 列表中。"

    parent_conversation_id = str(runtime_context.get("thread_id") or "") or None
    parent_run_id = str(runtime_context.get("run_id") or "") or None
    sub_run_id = uuid4().hex
    sub_started_at = time.perf_counter()

    # 第二层校验：模板必须存在，并且明确声明自己可以作为子 Agent 被调用。
    # 校验通过后立即写入 agent_runs(run_type=sub)，保证后续模型调用失败也能追踪到这次子任务。
    with get_db_session() as db:
        template_service = AgentTemplateService()
        template_view = template_service.get_template(db, agent_id)
        if template_view is None:
            return f"错误：子 Agent {agent_id} 的模板不存在或已被删除。"

        config = template_view.config
        if not config.is_sub_agent:
            return f"错误：Agent {agent_id} 未声明为可被 A2A 调用的子 Agent。"

        AgentRunService().create_running(
            db,
            run_id=sub_run_id,
            run_type="sub",
            parent_run_id=parent_run_id,
            agent_id=agent_id,
            conversation_id=parent_conversation_id,
            query=query,
            metadata={"source": "a2a_call"},
        )

    # 子 Agent 不传 conversation_id，因此 AgentAssembler 不会挂 PostgreSQL checkpointer。
    # db=None 表示不写 agent_conversations/agent_messages，也不额外创建主运行记录。
    sub_request = AgentRunRequest(
        query=query,
        conversation_id=None,
        system_prompt=config.system_prompt,
        response_format=config.response_format,
        tools=list(config.tools or []),
        optional_features=AgentOptionalFeatures(long_term_memory_enabled=False),
        runtime_options=config.runtime_options,
        a2a=None,
    )

    sub_service = AgentService()
    try:
        response = await sub_service.run(sub_request, db=None)
        elapsed_ms = (time.perf_counter() - sub_started_at) * 1000
        _mark_agent_run_success(sub_run_id, response.answer, elapsed_ms)
        return response.answer
    except Exception as error:
        elapsed_ms = (time.perf_counter() - sub_started_at) * 1000
        logger.exception("A2A sub-agent call failed: agent_id=%s sub_run_id=%s", agent_id, sub_run_id)
        _mark_agent_run_failed(sub_run_id, str(error), elapsed_ms)
        return f"子 Agent 调用失败：{error}"