from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class JobRawRecordListResponse(BaseModel):
    """原始岗位分页列表响应模型。"""

    items: list[JobRawRecordResponse] = Field(default_factory=list, description="原始岗位列表")
    total: int = Field(description="符合条件的原始岗位总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


class JobDirectionResponse(BaseModel):
    """岗位方向响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str | None = None
    description: str | None = None
    parent_id: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class JobDirectionListResponse(BaseModel):
    """岗位方向分页列表响应模型。"""

    items: list[JobDirectionResponse] = Field(default_factory=list, description="岗位方向列表")
    total: int = Field(description="符合条件的岗位方向总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


class JobMarketProfileResponse(BaseModel):
    """岗位聚合画像响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str | None = None
    profile_type: str
    job_name: str
    job_overview: str | None = None
    responsibilities: list[Any] | None = None
    required_skills: list[Any] | None = None
    preferred_skills: list[Any] | None = None
    education_requirement: str | None = None
    experience_requirement: str | None = None
    certificate_requirement: str | None = None
    created_at: datetime
    updated_at: datetime


class JobMarketProfileListResponse(BaseModel):
    """用户岗位画像分页列表响应模型。"""

    items: list[JobMarketProfileResponse] = Field(default_factory=list, description="用户岗位画像列表")
    total: int = Field(description="符合条件的岗位画像总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


class JobProfileGenerateResponse(BaseModel):
    """岗位画像 Agent 生成结果响应模型。"""

    run_id: str = Field(description="Agent 本次运行 ID，用于运行记录追踪")
    answer: str = Field(description="Agent 根据岗位画像保存结果生成的最终回复")


class JobCrawlIngestResponse(BaseModel):
    """岗位采集并写入原始岗位池的编排响应模型。"""

    platform: str = Field(description="招聘平台名称")
    total: int = Field(description="本次接口返回的岗位数量")
    rows: list[dict[str, Any]] = Field(default_factory=list, description="返回给调用方的岗位数据")
    csv_path: str | None = Field(default=None, description="CSV 输出路径")
    excel_path: str | None = Field(default=None, description="Excel 输出路径")
    crawl_run_id: int | None = Field(default=None, description="编排层创建的爬虫运行记录 ID")
    ingest_stats: dict[str, int] | None = Field(default=None, description="原始岗位入库统计信息")
