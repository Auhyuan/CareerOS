from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobSkillSearchRequest(BaseModel):
    """岗位技能批量查询请求。"""

    keywords: list[str] = Field(
        min_length=1, description="技能查询关键字列表"
    )
    limit_per_keyword: int = Field(default=10, ge=1, le=20, description="每个关键字最大返回数量")

    @field_validator("keywords")
    @classmethod
    def strip_keywords(cls, value: list[str]) -> list[str]:
        """清理关键字，去除空白和空字符串。"""
        cleaned = [kw.strip() for kw in value if kw.strip()]
        if not cleaned:
            raise ValueError("keywords 至少需要一个非空关键字")
        return cleaned


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


class JobSkillKeywordResult(BaseModel):
    """单个关键字的查询结果。"""

    keyword: str = Field(description="查询关键字")
    items: list[JobSkillResponse] = Field(default_factory=list, description="匹配技能列表")
    total: int = Field(default=0, description="匹配数量")


class JobSkillSearchResponse(BaseModel):
    """岗位技能批量查询结果。"""

    results: list[JobSkillKeywordResult] = Field(default_factory=list, description="每个关键字的查询结果")


class JobSkillCreateResponse(BaseModel):
    """岗位技能创建结果。"""

    skill: JobSkillResponse = Field(description="创建或复用的岗位技能")
    created: bool = Field(description="本次是否创建了新技能")


class JobSkillBatchCreateRequest(BaseModel):
    """岗位技能批量创建请求。"""

    items: list[JobSkillCreateRequest] = Field(
        min_length=1,
        max_length=100,
        description="待创建或复用的岗位技能列表，单次最多 100 条",
    )

    @field_validator("items")
    @classmethod
    def dedupe_items(cls, value: list[JobSkillCreateRequest]) -> list[JobSkillCreateRequest]:
        """
        按技能名称清理重复项，避免同一次请求重复创建同一个技能。

        Args:
            value: 调用方传入的技能创建列表。

        Returns:
            按名称去重后的技能创建列表。
        """
        seen_names: set[str] = set()
        unique_items: list[JobSkillCreateRequest] = []
        for item in value:
            key = item.name.strip().casefold()
            if key in seen_names:
                continue
            seen_names.add(key)
            unique_items.append(item)
        return unique_items


class JobSkillBatchCreateResponse(BaseModel):
    """岗位技能批量创建结果。"""

    requested: int = Field(description="请求中包含的技能数量（按名称去重后）")
    created: int = Field(description="本次实际新建的技能数量")
    reused: int = Field(description="本次复用已有技能的数量")
    results: list[JobSkillCreateResponse] = Field(default_factory=list, description="每个技能的创建或复用结果")


class JobSkillBatchDeleteRequest(BaseModel):
    """岗位技能批量删除请求。"""

    skill_ids: list[int] = Field(
        min_length=1,
        max_length=500,
        description="待删除的岗位技能 ID 列表，单次最多 500 条",
    )

    @field_validator("skill_ids")
    @classmethod
    def validate_skill_ids(cls, value: list[int]) -> list[int]:
        """
        校验技能 ID 列表，去重并保证全部为正整数。

        Args:
            value: 调用方传入的技能 ID 列表。

        Returns:
            去重后保序的技能 ID 列表。
        """
        if any(skill_id <= 0 for skill_id in value):
            raise ValueError("skill_ids 只能包含正整数")
        # 保序去重，避免同一条 ID 被重复删除。
        seen: set[int] = set()
        unique_ids: list[int] = []
        for skill_id in value:
            if skill_id not in seen:
                seen.add(skill_id)
                unique_ids.append(skill_id)
        return unique_ids


class JobSkillBatchDeleteResponse(BaseModel):
    """岗位技能批量删除结果。"""

    requested: int = Field(description="请求中包含的技能 ID 数量（去重后）")
    deleted: int = Field(description="本次实际删除的技能数量")
    deleted_ids: list[int] = Field(default_factory=list, description="本次已删除的技能 ID")
    missing_ids: list[int] = Field(
        default_factory=list,
        description="请求中提供但数据库中不存在的技能 ID",
    )
