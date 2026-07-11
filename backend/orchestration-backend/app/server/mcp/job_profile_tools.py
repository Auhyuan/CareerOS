from typing import Any, Literal

from app.common.db.postgres_db import get_db_session
from app.server.job.src.schemas.job_profile import JobProfileSaveRequest
from app.server.job.src.schemas.response import JobMarketProfileResponse
from app.server.job.src.service.job_profile_service import JobProfileService


def register_job_profile_tools(mcp: Any) -> None:
    """把岗位画像写入工具注册到 FastMCP 服务中。

    Args:
        mcp: FastMCP 服务实例。
    """
    service = JobProfileService()

    @mcp.tool(
        name="save_job_profile",
        description=(
            "保存已经完成提炼和技能标准化的岗位画像。"
            "profile_type 和 user_id 由系统运行上下文自动注入，模型不需要也不应该填写。"
            "调用前必须先通过 search_job_skills/create_job_skills 获得每项技能的有效 skill_id。"
            "只有该工具返回 saved=true 和 profile_id 后，岗位画像生成任务才算完成。"
        ),
    )
    async def save_job_profile(
        job_name: str,
        profile_type: Literal["user", "system"] | None = None,
        user_id: str | None = None,
        job_overview: str | None = None,
        responsibilities: list[dict[str, Any]] | None = None,
        required_skills: list[dict[str, Any]] | None = None,
        preferred_skills: list[dict[str, Any]] | None = None,
        education_requirement: str | None = None,
        experience_requirement: str | None = None,
        certificate_requirement: str | None = None,
    ) -> dict[str, Any]:
        """校验并保存一条用户或系统岗位画像。

        Args:
            job_name: Agent 从岗位材料中提炼的岗位名称。
            profile_type: 系统从 Agent Runtime Context 自动注入，模型不需要填写。
            user_id: 系统从 Agent Runtime Context 自动注入，模型不需要填写。
            job_overview: 岗位概述。
            responsibilities: 岗位职责列表，每项包含 name 和 description。
            required_skills: 必备技能列表，每项必须包含有效 skill_id、name 和 level。
            preferred_skills: 加分技能列表，每项必须包含有效 skill_id、name 和 level。
            education_requirement: 学历要求；材料未明确时为空。
            experience_requirement: 经验要求；材料未明确时为空。
            certificate_requirement: 证书要求；材料未明确时为空。

        Returns:
            保存状态、岗位画像 ID 以及数据库中的完整岗位画像。
        """
        request = JobProfileSaveRequest(
            profile_type=profile_type,
            user_id=user_id,
            profile={
                "job_name": job_name,
                "job_overview": job_overview,
                "responsibilities": responsibilities or [],
                "required_skills": required_skills or [],
                "preferred_skills": preferred_skills or [],
                "education_requirement": education_requirement,
                "experience_requirement": experience_requirement,
                "certificate_requirement": certificate_requirement,
            },
        )
        with get_db_session() as db:
            saved_profile = service.save_profile(db, request)
            profile_view = JobMarketProfileResponse.model_validate(saved_profile)
        return {
            "saved": True,
            "profile_id": profile_view.id,
            "profile": profile_view.model_dump(mode="json"),
        }
