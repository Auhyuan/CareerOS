import json
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field

from app.common.db.postgres_db import get_db_session
from app.server.job.src.schemas.job_profile import (
    JobProfileSaveRequest,
    JobResponsibility,
    PreferredSkill,
    RequiredSkill,
)
from app.server.job.src.schemas.response import JobMarketProfileResponse
from app.server.job.src.service.job_profile_service import JobProfileService


def _parse_json_array_argument(value: Any) -> Any:
    """把模型二次序列化的 JSON 数组字符串恢复为原生数组。

    Args:
        value: MCP 工具收到的原始参数。

    Returns:
        原生列表、None，或交给后续 Pydantic 校验的其他值。

    Raises:
        ValueError: 字符串不是合法 JSON，或解析结果不是数组。
    """
    if value is None or isinstance(value, list):
        return value
    if not isinstance(value, str):
        return value

    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("参数必须是原生数组或合法的 JSON 数组字符串") from error
    if not isinstance(parsed_value, list):
        raise ValueError("JSON 字符串解析后的结果必须是数组")
    return parsed_value


ResponsibilitiesArgument = Annotated[
    list[JobResponsibility] | None,
    BeforeValidator(_parse_json_array_argument),
    Field(max_length=15),
]
RequiredSkillsArgument = Annotated[
    list[RequiredSkill] | None,
    BeforeValidator(_parse_json_array_argument),
]
PreferredSkillsArgument = Annotated[
    list[PreferredSkill] | None,
    BeforeValidator(_parse_json_array_argument),
    Field(max_length=20),
]


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
            "调用前必须通过 search_job_skills/create_job_skills 获得每项技能的有效 skill_id 和标准 name。"
            "responsibilities、required_skills、preferred_skills 必须直接传原生 JSON 数组，禁止把数组序列化为字符串。"
            "正确示例：{\"job_name\":\"AI应用开发工程师\","
            "\"responsibilities\":[{\"name\":\"接口开发\",\"description\":\"开发AI应用接口\"}],"
            "\"required_skills\":[{\"skill_id\":66,\"name\":\"Python\",\"level\":3}],"
            "\"preferred_skills\":[]}。"
            "错误示例：{\"required_skills\":\"[{...}]\"}，这里的数组被错误地放进了字符串。"
            "只有返回 saved=true 和 profile_id 才表示成功；成功后不得再次调用，避免重复入库。"
        ),
    )
    async def save_job_profile(
        job_name: str,
        profile_type: Literal["user", "system"] | None = None,
        user_id: str | None = None,
        job_overview: str | None = None,
        responsibilities: ResponsibilitiesArgument = None,
        required_skills: RequiredSkillsArgument = None,
        preferred_skills: PreferredSkillsArgument = None,
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
                "responsibilities": [item.model_dump() for item in responsibilities or []],
                "required_skills": [item.model_dump() for item in required_skills or []],
                "preferred_skills": [item.model_dump() for item in preferred_skills or []],
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
