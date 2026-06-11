from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobPostingResponse(BaseModel):
    """岗位主表响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    platform_job_id: str | None = None
    source_url: str | None = None

    job_title_raw: str | None = None
    job_title_standard: str | None = None
    company_name: str | None = None

    city: str | None = None
    location: str | None = None

    salary_text: str | None = None
    salary_min_k: Decimal | None = None
    salary_max_k: Decimal | None = None

    experience_text: str | None = None
    experience_min_years: Decimal | None = None
    experience_max_years: Decimal | None = None

    education_text: str | None = None
    employment_type: str | None = None
    industry: str | None = None
    company_size: str | None = None

    job_description: str | None = None
    published_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    status: str
    raw_record_id: int | None = None
    created_at: datetime
    updated_at: datetime


class JobPostingListResponse(BaseModel):
    """岗位分页列表响应模型。"""

    items: list[JobPostingResponse] = Field(default_factory=list, description="岗位列表")
    total: int = Field(description="符合条件的岗位总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


class JobRawRecordResponse(BaseModel):
    """原始岗位记录响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    crawl_run_id: int | None = None
    platform: str
    platform_job_id: str | None = None
    source_url: str | None = None
    raw_title: str | None = None
    raw_company_name: str | None = None
    raw_city: str | None = None
    job_description: str | None = None
    raw_json: dict[str, Any]
    content_hash: str | None = None
    collected_at: datetime
    created_at: datetime
