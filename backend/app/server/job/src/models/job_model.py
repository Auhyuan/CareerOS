from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def now_time() -> datetime:
    """返回当前时间，用作模型默认时间字段。"""
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


class JobPosting(SQLModel, table=True):
    """岗位主表模型，对应 job_postings。"""

    __tablename__ = "job_postings"

    id: int | None = Field(default=None, primary_key=True)
    platform: str = Field(max_length=50)
    platform_job_id: str | None = Field(default=None, max_length=100)
    source_url: str | None = Field(default=None)

    job_title_raw: str | None = Field(default=None, max_length=500)
    job_title_standard: str | None = Field(default=None, max_length=255)
    company_name: str | None = Field(default=None, max_length=500)

    city: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)

    salary_text: str | None = Field(default=None, max_length=100)
    salary_min_k: Decimal | None = Field(default=None)
    salary_max_k: Decimal | None = Field(default=None)

    experience_text: str | None = Field(default=None, max_length=100)
    experience_min_years: Decimal | None = Field(default=None)
    experience_max_years: Decimal | None = Field(default=None)

    education_text: str | None = Field(default=None, max_length=100)
    employment_type: str | None = Field(default=None, max_length=100)

    industry: str | None = Field(default=None, max_length=255)
    company_size: str | None = Field(default=None, max_length=100)

    job_description: str | None = Field(default=None)
    published_at: datetime | None = Field(default=None)
    first_seen_at: datetime = Field(default_factory=now_time)
    last_seen_at: datetime = Field(default_factory=now_time)
    status: str = Field(default="recruiting", max_length=30)

    raw_record_id: int | None = Field(default=None, foreign_key="job_raw_records.id")
    created_at: datetime = Field(default_factory=now_time)
    updated_at: datetime = Field(default_factory=now_time)


class JobRequirementAnalysis(SQLModel, table=True):
    """JD 结构化分析表模型，对应 job_requirement_analysis。"""

    __tablename__ = "job_requirement_analysis"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job_postings.id")

    required_skills: list[Any] | None = Field(default=None, sa_column=Column(JSONB))
    preferred_skills: list[Any] | None = Field(default=None, sa_column=Column(JSONB))
    responsibilities: list[Any] | None = Field(default=None, sa_column=Column(JSONB))
    requirements: list[Any] | None = Field(default=None, sa_column=Column(JSONB))

    education_level: str | None = Field(default=None, max_length=100)
    experience_level: str | None = Field(default=None, max_length=100)
    difficulty_level: int | None = Field(default=None)
    job_direction: str | None = Field(default=None, max_length=100)
    job_category: str | None = Field(default=None, max_length=100)

    summary: str | None = Field(default=None)
    model_name: str | None = Field(default=None, max_length=100)
    analysis_version: str | None = Field(default=None, max_length=50)

    created_at: datetime = Field(default_factory=now_time)
    updated_at: datetime = Field(default_factory=now_time)
