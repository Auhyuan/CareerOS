from typing import Any

from app.common.db.postgres_db import get_db_session
from app.server.job.src.schemas.job_skill import JobSkillCreateRequest, JobSkillSearchRequest
from app.server.job.src.service.job_skill_service import JobSkillService


def register_job_skill_tools(mcp: Any) -> None:
    """把岗位技能相关工具注册到 FastMCP 服务中。

    Args:
        mcp: FastMCP 服务实例。这里保持宽松类型，避免未安装 FastMCP 时导入本模块就失败。
    """
    service = JobSkillService()

    @mcp.tool(
        name="search_job_skills",
        description=(
            "根据多个关键词批量查询平台已有岗位技能。"
            "创建新技能前应先调用该工具，返回结果会按关键词分组，并包含候选技能 ID。"
        ),
    )
    async def search_job_skills(keywords: list[str], limit_per_keyword: int = 10) -> dict[str, Any]:
        """从业务编排层数据库中查询平台岗位技能。

        Args:
            keywords: 需要批量查询的技能关键词列表。
            limit_per_keyword: 每个关键词最多返回的候选技能数量。

        Returns:
            可 JSON 序列化的分组技能查询结果。
        """
        request = JobSkillSearchRequest(keywords=keywords, limit_per_keyword=limit_per_keyword)
        with get_db_session() as db:
            result = service.search_skills(db, request)
        return result.model_dump(mode="json")

    @mcp.tool(
        name="create_job_skill",
        description=(
            "当 search_job_skills 没有找到语义相同的技能时，创建新的平台岗位技能。"
            "如果标准化名称已存在，会复用已有技能，并返回 created=false。"
        ),
    )
    async def create_job_skill(name: str, description: str) -> dict[str, Any]:
        """创建或复用平台岗位技能。

        Args:
            name: 技能标准名称。
            description: 简洁的技能描述。

        Returns:
            可 JSON 序列化的技能信息和是否新建标记。
        """
        request = JobSkillCreateRequest(name=name, description=description)
        with get_db_session() as db:
            result = service.create_skill(db, request)
        return result.model_dump(mode="json")
