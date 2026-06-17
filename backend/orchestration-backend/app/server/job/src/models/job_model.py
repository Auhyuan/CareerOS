from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def now_time() -> datetime:
    """返回当前时间，用作数据库模型的默认时间。"""
    return datetime.now()


class SpiderCrawlRun(SQLModel, table=True):
    """爬虫运行记录表模型，对应 spider_crawl_runs。"""

    __tablename__ = "spider_crawl_runs"

    id: int | None = Field(default=None, primary_key=True)
    platform: str = Field(max_length=50)
    keyword: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    pages: int | None = Field(default=1)
    status: str = Field(default="running", max_length=30)
    total_count: int | None = Field(default=0)
    request_params: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    error_message: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=now_time)


class JobRawRecord(SQLModel, table=True):
    """原始岗位数据表模型，对应 job_raw_records。"""

    __tablename__ = "job_raw_records"

    id: int | None = Field(default=None, primary_key=True)
    crawl_run_id: int | None = Field(default=None, foreign_key="spider_crawl_runs.id")
    platform: str = Field(max_length=50)
    platform_job_id: str | None = Field(default=None, max_length=100)
    source_url: str | None = Field(default=None)
    raw_title: str | None = Field(default=None, max_length=500)
    raw_company_name: str | None = Field(default=None, max_length=500)
    raw_city: str | None = Field(default=None, max_length=100)
    job_description: str | None = Field(default=None)
    raw_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    content_hash: str | None = Field(default=None, max_length=64)
    collected_at: datetime = Field(default_factory=now_time)
    created_at: datetime = Field(default_factory=now_time)


class JobDirection(SQLModel, table=True):
    """平台定义的岗位方向字典表模型，对应 job_directions。"""

    __tablename__ = "job_directions"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    code: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None)
    parent_id: int | None = Field(default=None, foreign_key="job_directions.id")
    status: str = Field(default="active", max_length=30)
    created_at: datetime = Field(default_factory=now_time)
    updated_at: datetime = Field(default_factory=now_time)


class JobMarketProfile(SQLModel, table=True):
    """岗位聚合画像表模型，对应 job_market_profiles。"""

    __tablename__ = "job_market_profiles"

    id: int | None = Field(default=None, primary_key=True)
    direction_id: int = Field(foreign_key="job_directions.id")
    job_name: str = Field(max_length=255)

    job_overview: str | None = Field(default=None)
    responsibilities: list[Any] | None = Field(default=None, sa_column=Column(JSONB))
    required_skills: list[Any] | None = Field(default=None, sa_column=Column(JSONB))
    preferred_skills: list[Any] | None = Field(default=None, sa_column=Column(JSONB))

    education_requirement: str | None = Field(default=None)
    experience_requirement: str | None = Field(default=None)
    certificate_requirement: str | None = Field(default=None)

    source_job_ids: list[Any] | None = Field(default=None, sa_column=Column(JSONB))
    source_filters: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))

    model_name: str | None = Field(default=None, max_length=100)
    analysis_version: str | None = Field(default=None, max_length=50)

    created_at: datetime = Field(default_factory=now_time)
    updated_at: datetime = Field(default_factory=now_time)
