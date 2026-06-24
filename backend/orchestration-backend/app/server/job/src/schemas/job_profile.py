from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobProfileGenerateRequest(BaseModel):
    """岗位画像统一生成请求，根据画像类型进入不同生成路线。"""

    profile_type: Literal["user", "system"] = Field(description="画像类型：user 或 system")
    agent_id: str = Field(
        min_length=1,
        max_length=100,
        description="本次岗位画像生成使用的 Agent 模板 ID",
    )

    # user 路线参数在统一请求中保持可选，进入 user 路线后再执行组合校验。
    user_id: str | None = Field(default=None, max_length=100, description="用户 ID；user 路线必填")
    job_text: str | None = Field(default=None, max_length=50000, description="岗位相关文本；user 路线必填")
    use_system_job_data: bool = Field(
        default=False,
        description="user 路线是否参考系统岗位数据；当前暂未启用",
    )

    # system 路线参数将在系统画像生成方案确定后继续补充。

    @field_validator("agent_id")
    @classmethod
    def strip_agent_id(cls, value: str) -> str:
        """
        清理 Agent 模板 ID，并禁止传入纯空白内容。

        Args:
            value: 调用方指定的 Agent 模板 ID。

        Returns:
            清理后的 Agent 模板 ID。
        """
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("agent_id 不能为空")
        return cleaned_value

    @field_validator("user_id", "job_text")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        """
        清理可选文本首尾空白，纯空白内容转换为 None。
        Args:
            value: 请求中的文本字段值。
        Returns:
            清理后的文本或 None。
        """
        if value is None:
            return None
        cleaned_value = value.strip()
        return cleaned_value or None


class UserJobProfileSearchRequest(BaseModel):
    """根据用户 ID 分页查询用户岗位画像的请求模型。"""

    user_id: str = Field(min_length=1, max_length=100, description="用户 ID")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")

    @field_validator("user_id")
    @classmethod
    def strip_user_id(cls, value: str) -> str:
        """
        清理用户 ID 首尾空白并禁止纯空白值。

        Args:
            value: 调用方传入的用户 ID。

        Returns:
            清理后的用户 ID。
        """
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("user_id 不能为空")
        return cleaned_value


class JobResponsibility(BaseModel):
    """Agent 输出的岗位职责结构。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None


class RequiredSkill(BaseModel):
    """Agent 输出的岗位必备技能结构。"""

    model_config = ConfigDict(extra="forbid")

    skill_id: int = Field(gt=0, description="平台 job_skills 表中的技能 ID")
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    level: int = Field(default=0, ge=0, description="技能等级：0=未明确，1=了解，2=熟悉，3=掌握，4=精通")
    requirement: str | None = Field(default=None, description="根据岗位原文提炼的具体技能要求")
    knowledge_points: list[str] = Field(default_factory=list, max_length=20)
    tools: list[str] = Field(default_factory=list, max_length=20)


class PreferredSkill(BaseModel):
    """Agent 输出的岗位加分技能结构。"""

    model_config = ConfigDict(extra="forbid")

    skill_id: int = Field(gt=0, description="平台 job_skills 表中的技能 ID")
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    level: int = Field(default=0, ge=0, description="技能等级：0=未明确，1=了解，2=熟悉，3=掌握，4=精通")
    requirement: str | None = Field(default=None, description="根据岗位原文提炼的具体技能要求")
    tools: list[str] = Field(default_factory=list, max_length=20)


class GeneratedJobProfile(BaseModel):
    """Agent 根据用户岗位材料生成的岗位画像业务内容。"""

    model_config = ConfigDict(extra="forbid")

    job_name: str = Field(min_length=1, max_length=255)
    job_overview: str | None = None
    responsibilities: list[JobResponsibility] = Field(default_factory=list, max_length=15)
    required_skills: list[RequiredSkill] = Field(default_factory=list, max_length=30)
    preferred_skills: list[PreferredSkill] = Field(default_factory=list, max_length=20)
    education_requirement: str | None = None
    experience_requirement: str | None = None
    certificate_requirement: str | None = None

    @field_validator("job_name")
    @classmethod
    def strip_job_name(cls, value: str) -> str:
        """
        清理岗位名称并确保名称非空。
        Args:
            value: Agent 生成的岗位名称。
        Returns:
            清理后的岗位名称。
        """
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("job_name 不能为空")
        return cleaned_value


class JobProfileBatchDeleteRequest(BaseModel):
    """岗位画像批量删除请求。"""

    profile_ids: list[int] = Field(
        min_length=1,
        max_length=500,
        description="待删除的岗位画像 ID 列表，单次最多 500 条",
    )

    @field_validator("profile_ids")
    @classmethod
    def validate_profile_ids(cls, value: list[int]) -> list[int]:
        """
        校验画像 ID 列表，去重并保证全部为正整数。

        Args:
            value: 调用方传入的画像 ID 列表。

        Returns:
            去重后保序的画像 ID 列表。
        """
        if any(profile_id <= 0 for profile_id in value):
            raise ValueError("profile_ids 只能包含正整数")
        # 保序去重，避免同一条 ID 被重复删除。
        seen: set[int] = set()
        unique_ids: list[int] = []
        for profile_id in value:
            if profile_id not in seen:
                seen.add(profile_id)
                unique_ids.append(profile_id)
        return unique_ids


class JobProfileBatchDeleteResponse(BaseModel):
    """岗位画像批量删除结果。"""

    requested: int = Field(description="请求中包含的画像 ID 数量（去重后）")
    deleted: int = Field(description="本次实际删除的画像数量")
    deleted_ids: list[int] = Field(default_factory=list, description="本次已删除的画像 ID")
    missing_ids: list[int] = Field(
        default_factory=list,
        description="请求中提供但数据库中不存在的画像 ID",
    )
