from typing import Any

import httpx
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, Field, field_validator

from app.server.agent.src.tools.job_tools.config import get_job_tool_config


class SearchJobSkillsInput(BaseModel):
    """查询岗位技能工具参数。"""

    keyword: str = Field(min_length=1, max_length=255, description="需要查询的技能名称或关键字")
    limit: int = Field(default=10, ge=1, le=20, description="最大返回数量")

    @field_validator("keyword")
    @classmethod
    def strip_keyword(cls, value: str) -> str:
        """
        清理技能查询关键字并禁止纯空白内容。

        Args:
            value: Agent 提供的技能查询关键字。

        Returns:
            清理后的查询关键字。
        """
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("keyword 不能为空")
        return cleaned_value


class CreateJobSkillInput(BaseModel):
    """创建岗位技能工具参数。"""

    name: str = Field(min_length=1, max_length=255, description="技能标准名称")
    description: str = Field(min_length=1, max_length=2000, description="准确、简洁的技能描述")

    @field_validator("name", "description")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """
        清理技能名称和描述并禁止纯空白内容。

        Args:
            value: Agent 提供的技能名称或描述。

        Returns:
            清理后的文本。
        """
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("字段不能为空")
        return cleaned_value


async def _post_job_api(
    *,
    path: str,
    payload: dict[str, Any],
    operation_name: str,
) -> dict[str, Any]:
    """
    调用业务编排层 Job API 并解析统一响应。

    Args:
        path: Job API 路径。
        payload: POST 请求体。
        operation_name: 用于异常提示的操作名称。

    Returns:
        统一响应中的 data 字典。

    Raises:
        RuntimeError: HTTP 调用失败、响应格式异常或业务 code 非零。
    """
    config = get_job_tool_config()
    url = f"{config.orchestration_base_url.rstrip('/')}{path}"

    try:
        async with httpx.AsyncClient(timeout=config.orchestration_timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise RuntimeError(f"{operation_name}失败: {error}") from error

    try:
        body = response.json()
    except ValueError as error:
        raise RuntimeError(f"{operation_name}接口返回内容不是合法 JSON") from error

    if not isinstance(body, dict):
        raise RuntimeError(f"{operation_name}接口返回结构异常")
    if body.get("code") != 0:
        raise RuntimeError(body.get("msg") or f"{operation_name}接口返回失败")

    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"{operation_name}接口返回 data 结构异常")
    return data


def _format_skill_results(keyword: str, data: dict[str, Any]) -> str:
    """将技能查询结果格式化为检索上下文文本。

    Args:
        keyword: 查询关键字。
        data: Job API 返回的 data 字典。

    Returns:
        格式化后的检索上下文文本。
    """
    items = data.get("items") or []
    total = data.get("total", 0)
    if not items:
        return f"技能查询「{keyword}」：未找到匹配结果。"

    lines = [f"技能查询「{keyword}」共 {total} 条结果（展示前 {len(items)} 条）："]
    for idx, item in enumerate(items, start=1):
        name = item.get("name", "未知")
        skill_id = item.get("id") or item.get("skill_id", "-")
        desc = item.get("description", "")
        desc_text = desc[:200] if desc else "无描述"
        lines.append(f"  {idx}. {name}（ID: {skill_id}）— {desc_text}")
    return "\n".join(lines)


@tool("search_job_skills", args_schema=SearchJobSkillsInput)
async def search_job_skills(keyword: str, limit: int = 10, runtime: ToolRuntime | None = None) -> Command | dict:
    """
    查询平台已存在的岗位技能。创建技能前必须先调用此工具，
    如果结果中存在语义相同的技能，应直接引用返回的技能 ID。

    检索结果通过 Command 写入 state.retrieval_context，
    由 InjectRetrievalContextMiddleware 注入到下一轮 system prompt。

    Args:
        keyword: 需要查询的技能名称或关键字。
        limit: 最大返回数量。
        runtime: LangGraph 工具运行时，用于获取 tool_call_id 和更新 state。

    Returns:
        Command 对象（LangGraph 环境）或 dict（非 LangGraph 兜底）。
    """
    data = await _post_job_api(
        path="/job/skills/search",
        payload={"keyword": keyword, "limit": limit},
        operation_name="查询岗位技能",
    )

    context_str = _format_skill_results(keyword, data)

    if runtime is not None:
        tool_call_id = getattr(runtime, "tool_call_id", None)
        return Command(update={
            "messages": [ToolMessage(
                content=f"技能查询完成，找到 {data.get('total', 0)} 条结果",
                tool_call_id=tool_call_id,
            )],
            "retrieval_context": context_str,
        })
    return data


@tool("create_job_skill", args_schema=CreateJobSkillInput)
async def create_job_skill(name: str, description: str) -> dict[str, Any]:
    """
    创建一个平台岗位技能。仅当 search_job_skills 未找到相同技能时调用；
    如果数据库中已经存在，接口会返回已有技能并将 created 标记为 false。

    Args:
        name: 技能标准名称。
        description: 准确、简洁的技能描述。

    Returns:
        Job 技能创建接口返回的技能和创建状态。
    """
    return await _post_job_api(
        path="/job/skills/create",
        payload={"name": name, "description": description},
        operation_name="创建岗位技能",
    )
