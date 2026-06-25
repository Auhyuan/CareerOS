"""A2A 工具：将子 Agent 调用包装为 BaseTool。"""

import logging
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class A2ACallInput(BaseModel):
    """A2A 工具调用参数。"""

    agent_id: str = Field(description="要调用的子 Agent ID")
    query: str = Field(description="传给子 Agent 的任务指令")


@tool("a2a_call", args_schema=A2ACallInput)
async def a2a_call(agent_id: str, query: str) -> str:
    """调用子 Agent 执行子任务。

    具体的子 Agent 列表和描述已注入到 system prompt 的 <a2a_instruct> 标签中，
    请根据该列表选择正确的 agent_id。子 Agent 返回文本结果，你需要整理后呈现给用户。
    """
    from sqlmodel import Session

    from app.common.db.postgres_db import get_postgres_engine
    from app.server.agent.src.agent.service import AgentService
    from app.server.agent.src.schemas.request import AgentRunRequest
    from app.server.agent.src.templates.service import AgentTemplateService

    engine = get_postgres_engine()
    with Session(engine) as db:
        template_service = AgentTemplateService()
        template_view = template_service.get_template(db, agent_id)
        if template_view is None:
            return f"错误：子 Agent「{agent_id}」的模板不存在或已被删除。"

        config = template_view.config

    # 子 Agent 以无状态执行
    sub_request = AgentRunRequest(
        query=query,
        conversation_id=None,
        stream=False,
        system_prompt=config.get("system_prompt"),
        response_format=config.get("response_format"),
        tools=list(config.get("tools") or []),
        optional_features=config.get("optional_features"),
        runtime_options=config.get("runtime_options"),
        a2a=None,
    )

    sub_service = AgentService()
    try:
        response = await sub_service.run(sub_request)
        return response.answer
    except Exception as error:
        logger.exception("A2A sub-agent call failed: agent_id=%s", agent_id)
        return f"子 Agent 调用失败：{error}"
