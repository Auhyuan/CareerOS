from pydantic import BaseModel, Field, field_validator


class SearchJobSkillsInput(BaseModel):
    """查询岗位技能工具参数。"""

    keyword: str = Field(min_length=1, max_length=255, description="需要查询的技能名称或关键字")
    limit: int = Field(default=10, ge=1, le=20, description="最大返回数量")

    @field_validator("keyword")
    @classmethod
    def strip_keyword(cls, value: str) -> str:
        """
        清理技能查询关键字并禁止纯空白内容。

        Args:
            value: Agent 提供的技能查询关键字。

        Returns:
            清理后的查询关键字。
        """
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("keyword 不能为空")
        return cleaned_value


class CreateJobSkillInput(BaseModel):
    """创建岗位技能工具参数。"""

    name: str = Field(min_length=1, max_length=255, description="技能标准名称")
    description: str = Field(min_length=1, max_length=2000, description="准确、简洁的技能描述")

    @field_validator("name", "description")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """
        清理技能名称和描述并禁止纯空白内容。

        Args:
            value: Agent 提供的技能名称或描述。

        Returns:
            清理后的文本。
        """
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("字段不能为空")
        return cleaned_value
