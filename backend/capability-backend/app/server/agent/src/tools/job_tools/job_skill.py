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
    """Call the orchestration Job API and unwrap the unified Result response.

    Args:
        path: Job API path, such as /job/skills/search.
        payload: JSON request body sent to the orchestration service.
        operation_name: Human-readable operation name used in error messages.

    Returns:
        The data object inside the unified API response.

    Raises:
        RuntimeError: Raised when HTTP, JSON decoding, response shape, or business code fails.
    """
    config = get_job_tool_config()
    url = f"{config.orchestration_base_url.rstrip('/')}{path}"

    try:
        async with httpx.AsyncClient(timeout=config.orchestration_timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise RuntimeError(f"{operation_name} failed: {error}") from error

    try:
        body = response.json()
    except ValueError as error:
        raise RuntimeError(f"{operation_name} returned invalid JSON") from error

    if not isinstance(body, dict):
        raise RuntimeError(f"{operation_name} returned an invalid response shape")
    if body.get("code") != 0:
        raise RuntimeError(body.get("msg") or f"{operation_name} returned a failure code")

    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"{operation_name} returned an invalid data object")
    return data


def _clean_keywords(keywords: list[str]) -> list[str]:
    """Normalize and validate skill search keywords before calling the Job API.

    Args:
        keywords: Raw keyword list supplied by the model or tool test UI.

    Returns:
        Trimmed non-empty keywords.

    Raises:
        RuntimeError: Raised when no usable keyword remains after cleanup.
    """
    cleaned_keywords = [item.strip() for item in keywords if isinstance(item, str) and item.strip()]
    if not cleaned_keywords:
        raise RuntimeError("keywords must contain at least one non-empty value")
    return cleaned_keywords


def _get_runtime_value(runtime: ToolRuntime, key: str, default: str = "") -> str:
    """Read a value from LangGraph ToolRuntime.context.

    Args:
        runtime: LangGraph-injected tool runtime. It must stay non-optional so LangGraph hides it from the model schema.
        key: Runtime context key to read.
        default: Value returned when the key is missing.

    Returns:
        Runtime context value converted to string.
    """
    context = getattr(runtime, "context", None)
    if context is None:
        return default
    if isinstance(context, dict):
        return str(context.get(key) or default)
    return str(getattr(context, key, default) or default)


def _format_skill_results(data: dict[str, Any]) -> str:
    """Format batched skill search results as retrieval context text.

    Args:
        data: Job API data object containing a results list.

    Returns:
        Text injected into the next model call by InjectRetrievalContextMiddleware.
    """
    results = data.get("results") or []
    if not results:
        return "Skill search: no matching result."

    sections: list[str] = []
    for result in results:
        keyword = result.get("keyword", "")
        items = result.get("items") or []
        total = result.get("total", 0)
        if not items:
            sections.append(f"Skill search for '{keyword}': no matching result.")
            continue

        lines = [f"Skill search for '{keyword}': {total} result(s), showing {len(items)} item(s):"]
        for idx, item in enumerate(items, start=1):
            name = item.get("name", "unknown")
            skill_id = item.get("id") or item.get("skill_id", "-")
            desc = item.get("description", "")
            desc_text = desc[:200] if desc else "no description"
            lines.append(f"  {idx}. {name} (ID: {skill_id}) - {desc_text}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


async def query_job_skills_data(keywords: list[str]) -> dict[str, Any]:
    """Query job skills and return raw API data for non-Agent callers.

    This helper is used by the tool management test API. It intentionally does not require ToolRuntime,
    because direct tool tests run outside LangGraph and therefore cannot receive runtime injection.

    Args:
        keywords: Skill keywords to search.

    Returns:
        Raw data object returned by the orchestration Job API.
    """
    cleaned_keywords = _clean_keywords(keywords)
    return await _post_job_api(
        path="/job/skills/search",
        payload={"keywords": cleaned_keywords, "limit_per_keyword": 10},
        operation_name="search job skills",
    )


@tool("search_job_skills")
async def search_job_skills(keywords: list[str], runtime: ToolRuntime) -> Command:
    """Search existing platform job skills and inject results into LangGraph state.

    Args:
        keywords: Skill keywords extracted by the model. Multiple keywords can be queried in one call.
        runtime: LangGraph-injected tool runtime. Keep this argument required and typed as ToolRuntime so it is hidden
            from the model-facing tool schema and Command state updates can work.

    Returns:
        A Command that appends a ToolMessage and writes retrieval_context for the next model turn.
    """
    data = await query_job_skills_data(keywords)
    context_str = _format_skill_results(data)

    # The tool only returns a short success ToolMessage to the model. The real search content is written
    # into retrieval_context, then InjectRetrievalContextMiddleware injects it before the next model call.
    total_count = sum(result.get("total", 0) for result in (data.get("results") or []))
    tool_call_id = runtime.tool_call_id
    run_id = _get_runtime_value(runtime, "run_id")
    return Command(update={
        "messages": [ToolMessage(
            content=f"Skill batch search completed, found {total_count} result(s).",
            tool_call_id=tool_call_id,
        )],
        "retrieval_context": [{"run_id": run_id, "content": context_str}],
    })


@tool("create_job_skill")
async def create_job_skill(name: str, description: str) -> dict[str, Any]:
    """Create a platform job skill through the orchestration Job API.

    Args:
        name: Standard skill name.
        description: Concise skill description.

    Returns:
        The created or reused skill and a created flag returned by the Job API.
    """
    cleaned_name = name.strip() if isinstance(name, str) else ""
    cleaned_description = description.strip() if isinstance(description, str) else ""
    if not cleaned_name or not cleaned_description:
        raise RuntimeError("name and description must be non-empty")

    return await _post_job_api(
        path="/job/skills/create",
        payload={"name": cleaned_name, "description": cleaned_description},
        operation_name="create job skill",
    )
