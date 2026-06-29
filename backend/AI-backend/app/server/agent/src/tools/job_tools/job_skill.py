import logging
from typing import Any

import httpx
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command

from app.server.agent.src.tools.job_tools.config import get_job_tool_config

logger = logging.getLogger(__name__)


async def _post_job_api(
    *,
    path: str,
    payload: dict[str, Any],
    operation_name: str,
) -> dict[str, Any]:
    """调用编排层 Job API，解析统一响应并返回 data 字段。

    Args:
        path: Job API 路径，如 /job/skills/search。
        payload: 请求体 JSON。
        operation_name: 操作名称，用于异常提示。

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
        raise RuntimeError(f"{operation_name}返回内容不是合法 JSON") from error

    if not isinstance(body, dict):
        raise RuntimeError(f"{operation_name}返回结构异常")
    if body.get("code") != 0:
        raise RuntimeError(body.get("msg") or f"{operation_name}返回失败")

    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"{operation_name}返回 data 结构异常")
    return data


def _clean_keywords(keywords: list[str]) -> list[str]:
    """清理并校验技能查询关键字。

    Args:
        keywords: 模型或工具测试页传入的原始关键字列表。

    Returns:
        去空白、去空字符串后的关键字列表。

    Raises:
        RuntimeError: 清理后无有效关键字时抛出。
    """
    cleaned_keywords = [item.strip() for item in keywords if isinstance(item, str) and item.strip()]
    if not cleaned_keywords:
        raise RuntimeError("keywords 至少需要一个非空关键字")
    return cleaned_keywords


def _get_runtime_value(runtime: ToolRuntime, key: str, default: str = "") -> str:
    """从 LangGraph ToolRuntime.context 中读取运行时变量。

    Args:
        runtime: LangGraph 注入的工具运行时，不可为 None，否则 LangGraph 会在模型 schema 中暴露该参数。
        key: 需要读取的运行时变量名。
        default: 变量不存在时的默认值。

    Returns:
        运行时变量转字符串。
    """
    context = getattr(runtime, "context", None)
    if context is None:
        return default
    if isinstance(context, dict):
        return str(context.get(key) or default)
    return str(getattr(context, key, default) or default)


def _format_skill_results(data: dict[str, Any]) -> str:
    """将批量技能查询结果格式化为检索上下文文本。

    Args:
        data: Job API 返回的 data 字典，含 results 列表。

    Returns:
        注入到下一轮系统提示词的检索内容文本。
    """
    results = data.get("results") or []
    if not results:
        return "技能查询：未找到匹配结果。"

    sections: list[str] = []
    for result in results:
        keyword = result.get("keyword", "")
        items = result.get("items") or []
        total = result.get("total", 0)
        if not items:
            sections.append(f"技能查询「{keyword}」：未找到匹配结果。")
            continue

        lines = [f"技能查询「{keyword}」共 {total} 条结果（展示前 {len(items)} 条）："]
        for idx, item in enumerate(items, start=1):
            name = item.get("name", "未知")
            skill_id = item.get("id") or item.get("skill_id", "-")
            desc = item.get("description", "")
            desc_text = desc[:200] if desc else "无描述"
            lines.append(f"  {idx}. {name}（ID: {skill_id}）— {desc_text}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


async def query_job_skills_data(keywords: list[str]) -> dict[str, Any]:
    """查询岗位技能并返回原始 API 数据，供非 Agent 调用方使用。

    工具管理页的调试调用不经过 LangGraph，无法接收 runtime 注入，
    因此单独提供此函数，不依赖 ToolRuntime。

    Args:
        keywords: 需要查询的技能关键字。

    Returns:
        Job API 返回的原始 data 字典。
    """
    cleaned_keywords = _clean_keywords(keywords)
    return await _post_job_api(
        path="/job/skills/search",
        payload={"keywords": cleaned_keywords, "limit_per_keyword": 10},
        operation_name="查询岗位技能",
    )


@tool("search_job_skills")
async def search_job_skills(keywords: list[str], runtime: ToolRuntime) -> Command:
    """批量查询平台已存在的岗位技能，并将结果注入 LangGraph state。

    工具只返回简短的成功提示给模型，实际检索内容写入 retrieval_context，
    由 InjectRetrievalContextMiddleware 在下一轮模型调用前注入到系统提示词。

    Args:
        keywords: 模型提取的技能关键字，可一次查询多个。
        runtime: LangGraph 注入的工具运行时。保持 required 并类型为 ToolRuntime，
            确保 LangGraph 不在模型可见的 tool schema 中暴露该参数。

    Returns:
        Command 对象，追加 ToolMessage 并写入 retrieval_context。
    """
    data = await query_job_skills_data(keywords)
    context_str = _format_skill_results(data)

    total_count = sum(result.get("total", 0) for result in (data.get("results") or []))
    tool_call_id = runtime.tool_call_id
    run_id = _get_runtime_value(runtime, "run_id")
    return Command(update={
        "messages": [ToolMessage(
            content=f"技能批量查询完成，共找到 {total_count} 条结果",
            tool_call_id=tool_call_id,
        )],
        "retrieval_context": [{"run_id": run_id, "content": context_str}],
    })


@tool("create_job_skill")
async def create_job_skill(name: str, description: str) -> dict[str, Any]:
    """通过编排层 Job API 创建平台岗位技能。

    仅当 search_job_skills 未找到相同技能时调用；
    如果数据库中已存在同名技能，接口会返回已有技能并将 created 标记为 false。

    Args:
        name: 技能标准名称。
        description: 简洁的技能描述。

    Returns:
        Job API 返回的技能和创建状态。
    """
    cleaned_name = name.strip() if isinstance(name, str) else ""
    cleaned_description = description.strip() if isinstance(description, str) else ""
    if not cleaned_name or not cleaned_description:
        raise RuntimeError("name 和 description 不能为空")

    return await _post_job_api(
        path="/job/skills/create",
        payload={"name": cleaned_name, "description": cleaned_description},
        operation_name="创建岗位技能",
    )
