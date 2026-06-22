from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from app.server.agent.src.tools.job_tools.client import JobToolClient
from app.server.agent.src.tools.job_tools.schemas import CreateJobSkillInput, SearchJobSkillsInput


def create_job_tools(client: JobToolClient | None = None) -> list[BaseTool]:
    """
    创建可装配到 LangChain Agent 的 Job 业务工具。

    Args:
        client: Job API 客户端；测试时可注入模拟客户端。

    Returns:
        查询岗位技能和创建岗位技能两个 LangChain 工具。
    """
    job_client = client or JobToolClient()

    async def search_job_skills(keyword: str, limit: int = 10) -> dict[str, Any]:
        """
        查询平台已存在的岗位技能。创建技能前必须先调用此工具，
        如果结果中存在语义相同的技能，应直接引用返回的技能 ID。
        """
        return await job_client.search_job_skills(keyword=keyword, limit=limit)

    async def create_job_skill(name: str, description: str) -> dict[str, Any]:
        """
        创建一个平台岗位技能。仅当 search_job_skills 未找到相同技能时调用；
        如果数据库中已经存在，接口会返回已有技能并将 created 标记为 false。
        """
        return await job_client.create_job_skill(name=name, description=description)

    search_tool = StructuredTool.from_function(
        coroutine=search_job_skills,
        name="search_job_skills",
        description=(
            "查询平台岗位技能。提取到技能后应先调用此工具查重；"
            "找到相同或等价技能时，直接使用返回的技能 id，不要重复创建。"
        ),
        args_schema=SearchJobSkillsInput,
    )
    create_tool = StructuredTool.from_function(
        coroutine=create_job_skill,
        name="create_job_skill",
        description=(
            "创建平台岗位技能。仅在 search_job_skills 没有找到相同技能时调用，"
            "需要提供规范技能名称和准确的技能描述。"
        ),
        args_schema=CreateJobSkillInput,
    )
    return [search_tool, create_tool]
