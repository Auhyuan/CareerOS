from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TemporaryJobProfileGenerateRequest(BaseModel):
    """用户临时岗位画像生成请求。"""

    user_id: str = Field(min_length=1, max_length=100, description="Java 层传入的用户 ID")
    job_text: str = Field(min_length=1, max_length=50000, description="用户提交的岗位相关文本")
    use_system_job_data: bool = Field(
        default=False,
        description="是否参考系统岗位数据；第一版暂未启用",
    )

    @field_validator("user_id", "job_text")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """
        清理必填文本首尾空白，并禁止纯空白内容。
        Args:
            value: 请求中的文本字段值。
        Returns:
            清理后的文本。
        """
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("字段不能为空")
        return cleaned_value


class JobResponsibility(BaseModel):
    """Agent 输出的岗位职责结构。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None


class RequiredSkill(BaseModel):
    """Agent 输出的岗位必备技能结构。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    level: Literal["了解", "熟悉", "熟练掌握", "能够独立应用"] | None = None
    requirement: str | None = None
    knowledge_points: list[str] = Field(default_factory=list, max_length=20)
    tools: list[str] = Field(default_factory=list, max_length=20)


class PreferredSkill(BaseModel):
    """Agent 输出的岗位加分技能结构。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    requirement: str | None = None
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
