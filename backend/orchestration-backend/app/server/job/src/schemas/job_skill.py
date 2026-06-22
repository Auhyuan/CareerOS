from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobSkillSearchRequest(BaseModel):
    """岗位技能查询请求。"""

    keyword: str = Field(min_length=1, max_length=255, description="技能查询关键字")
    limit: int = Field(default=10, ge=1, le=20, description="最大返回数量")

    @field_validator("keyword")
    @classmethod
    def strip_keyword(cls, value: str) -> str:
        """
        清理技能查询关键字并禁止纯空白内容。

        Args:
            value: 调用方传入的技能关键字。

        Returns:
            清理后的技能关键字。
        """
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("keyword 不能为空")
        return cleaned_value


class JobSkillCreateRequest(BaseModel):
    """岗位技能创建请求。"""

    name: str = Field(min_length=1, max_length=255, description="技能标准名称")
    description: str = Field(min_length=1, max_length=2000, description="技能描述")

    @field_validator("name", "description")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """
        清理技能创建文本并禁止纯空白内容。

        Args:
            value: 技能名称或技能描述。

        Returns:
            清理后的文本。
        """
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("字段不能为空")
        return cleaned_value


class JobSkillResponse(BaseModel):
    """岗位技能响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    normalized_name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class JobSkillSearchResponse(BaseModel):
    """岗位技能查询结果。"""

    items: list[JobSkillResponse] = Field(default_factory=list, description="匹配到的技能列表")
    total: int = Field(default=0, description="本次返回的技能数量")


class JobSkillCreateResponse(BaseModel):
    """岗位技能创建结果。"""

    skill: JobSkillResponse = Field(description="创建或复用的岗位技能")
    created: bool = Field(description="本次是否创建了新技能")
