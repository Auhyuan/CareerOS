from typing import Any

from app.common.db.postgres_db import get_db_session
from app.server.job.src.schemas.job_skill import JobSkillBatchCreateRequest, JobSkillSearchRequest
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
            "根据多个关键词一次性批量查询平台已有岗位技能。"
            "应先汇总并去重全部技能后再调用，返回结果按关键词分组。"
            "items 只是候选，调用方必须判断是否为同一技能；确认复用后使用候选项的 id 和标准 name。"
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
        name="create_job_skills",
        description=(
            "为 search_job_skills 未找到语义相同候选项的技能一次性批量创建平台技能。"
            "参数 skills 是数组，每项必须包含 name 和 description；不要把已确认可复用的技能再次创建。"
            "标准化名称已存在时会复用已有技能，调用方必须从 results 中读取 skill.id、skill.name 和 created。"
        ),
    )
    async def create_job_skills(skills: list[dict[str, str]]) -> dict[str, Any]:
        """批量创建或复用平台岗位技能。

        Args:
            skills: 技能列表；每项需要包含 name 和 description。

        Returns:
            可 JSON 序列化的批量创建结果，包含每条技能的 ID 和 created 标记。
        """
        request = JobSkillBatchCreateRequest(items=skills)
        with get_db_session() as db:
            result = service.batch_create_skills(db, request)
        return result.model_dump(mode="json")
