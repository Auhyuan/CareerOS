"""A2A 上下文中间件：获取子 Agent 元信息并注入到 system prompt。"""

import logging
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

from app.server.agent.src.graph.state import CareerAgentState

logger = logging.getLogger(__name__)


class A2AAgentContextMiddleware(AgentMiddleware[CareerAgentState]):
    """A2A 上下文注入中间件。

    在首次模型调用时从 DB 获取子 Agent 元信息（名称、描述），
    然后在 system prompt 中注入可用子 Agent 列表和使用规则。
    后续多次模型调用直接复用缓存，不会重复查 DB。
    """

    state_schema = CareerAgentState

    def __init__(self):
        self._metas: list[dict[str, str]] | None = None
        self.enabled = True

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """每次模型调用前检查并注入 A2A 上下文。"""
        # 首次调用时从 DB 加载子 Agent 元信息
        if self._metas is None:
            sub_agent_list = (request.runtime.context or {}).get("a2a_sub_agent_list", [])
            if sub_agent_list:
                self._metas = await self._load_sub_agent_metas(sub_agent_list)

        # 无子 Agent 则不注入
        if not self._metas:
            return await handler(request)

        # 注入到 system prompt
        injected = self._build_a2a_prompt(self._metas)
        current_prompt = getattr(request.system_message, "content", "")
        new_system = SystemMessage(content=f"{current_prompt}\n\n{injected}")
        return await handler(request.override(system_message=new_system))

    async def _load_sub_agent_metas(self, agent_ids: list[str]) -> list[dict[str, str]]:
        """从 DB 查询子 Agent 的名称和描述。

        Args:
            agent_ids: 子 Agent ID 列表。

        Returns:
            [{agent_id, agent_name, description}, ...]
            遇到不存在的 agent_id 时跳过并 warn。
        """
        from sqlmodel import Session

        from app.common.db.postgres_db import get_postgres_engine
        from app.server.agent.src.templates.service import AgentTemplateService

        metas: list[dict[str, str]] = []
        engine = get_postgres_engine()
        with Session(engine) as db:
            template_service = AgentTemplateService()
            for agent_id in agent_ids:
                template = template_service.get_template(db, agent_id)
                if template is None:
                    logger.warning("A2A sub-agent not found: agent_id=%s", agent_id)
                    continue
                metas.append({
                    "agent_id": template.agent_id,
                    "agent_name": template.agent_name,
                    "description": template.description or "",
                })

        return metas

    def _build_a2a_prompt(self, metas: list[dict[str, str]]) -> str:
        """构建注入 system prompt 的 A2A 上下文文本。"""
        agent_lines = []
        for meta in metas:
            agent_lines.append(
                f"- {meta['agent_name']}（agent_id: {meta['agent_id']}）: {meta['description']}"
            )

        return (
            f"<a2a_instruct>\n"
            f"你可以调用以下子 Agent 来完成子任务：\n"
            + "\n".join(agent_lines)
            + "\n\n使用规则：\n"
            "1. 使用 a2a_call 工具调用子 Agent\n"
            "2. 传入的 query 应清晰、具体，包含子 Agent 所需的全部信息\n"
            "3. 子 Agent 返回文本结果，你需要整理后呈现给用户\n"
            "</a2a_instruct>"
        )
