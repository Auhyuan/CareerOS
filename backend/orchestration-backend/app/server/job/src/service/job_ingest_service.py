from datetime import datetime
from typing import Any

from sqlmodel import Session

from app.server.job.src.config.job_config import (
    JOB_STATUS_RECRUITING,
    SPIDER_RUN_STATUS_FAILED,
    SPIDER_RUN_STATUS_RUNNING,
    SPIDER_RUN_STATUS_SUCCESS,
)
from app.server.job.src.models.job_model import JobPosting, JobRawRecord, SpiderCrawlRun
from app.server.job.src.repository.job_repository import JobRepository
from app.server.job.src.service.job_parser_service import JobParserService


class JobIngestService:
    """岗位采集结果入库服务，负责爬虫任务、原始记录和标准岗位表写入。"""

    def __init__(
        self,
        repository: JobRepository | None = None,
        parser_service: JobParserService | None = None,
    ):
        """
        初始化岗位入库服务。

        Args:
            repository: 岗位库数据访问对象。
            parser_service: 岗位字段解析服务。
        """
        self.repository = repository or JobRepository()
        self.parser_service = parser_service or JobParserService()

    def create_crawl_run(
        self,
        db: Session,
        *,
        platform: str,
        keywords: list[str],
        cities: list[str],
        pages: int,
        request_params: dict[str, Any],
    ) -> SpiderCrawlRun:
        """
        创建爬虫运行记录。

        Args:
            db: 数据库会话。
            platform: 招聘平台标识，例如 qcwy。
            keywords: 本次采集关键词列表。
            cities: 本次采集城市列表。
            pages: 每组关键词和城市采集页数。
            request_params: 接口请求参数快照。

        Returns:
            已保存的爬虫运行记录。
        """
        crawl_run = SpiderCrawlRun(
            platform=platform,
            keyword=",".join(keywords),
            city=",".join(cities),
            pages=pages,
            status=SPIDER_RUN_STATUS_RUNNING,
            total_count=0,
            request_params=request_params,
            started_at=datetime.now(),
        )
        return self.repository.create_crawl_run(crawl_run, db)

    def mark_crawl_run_success(self, db: Session, crawl_run_id: int, total_count: int) -> None:
        """
        标记爬虫任务成功。

        Args:
            db: 数据库会话。
            crawl_run_id: 爬虫运行记录 ID。
            total_count: 本次采集到的岗位数量。
        """
        self.repository.update_crawl_run(
            crawl_run_id,
            db,
            status=SPIDER_RUN_STATUS_SUCCESS,
            total_count=total_count,
            finished_at=datetime.now(),
        )

    def mark_crawl_run_failed(self, db: Session, crawl_run_id: int, error_message: str) -> None:
        """
        标记爬虫任务失败。

        Args:
            db: 数据库会话。
            crawl_run_id: 爬虫运行记录 ID。
            error_message: 失败原因。
        """
        self.repository.update_crawl_run(
            crawl_run_id,
            db,
            status=SPIDER_RUN_STATUS_FAILED,
            total_count=0,
            error_message=error_message,
            finished_at=datetime.now(),
        )

    def ingest_spider_rows(
        self,
        db: Session,
        *,
        crawl_run_id: int,
        platform: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, int]:
        """
        把爬虫采集结果写入原始表和岗位主表。

        Args:
            db: 数据库会话。
            crawl_run_id: 本次爬虫运行记录 ID。
            platform: 招聘平台标识，例如 qcwy。
            rows: 爬虫返回的岗位行列表。

        Returns:
            入库统计。
        """
        raw_created = 0
        posting_created = 0
        posting_updated = 0

        for row in rows:
            raw_record = self.create_raw_record_from_row(db, crawl_run_id, platform, row)
            raw_created += 1

            posting, created = self.upsert_posting_from_raw_record(db, raw_record, row)
            if posting and created:
                posting_created += 1
            elif posting:
                posting_updated += 1

        return {
            "raw_created": raw_created,
            "posting_created": posting_created,
            "posting_updated": posting_updated,
        }

    def create_raw_record_from_row(
        self,
        db: Session,
        crawl_run_id: int,
        platform: str,
        row: dict[str, Any],
    ) -> JobRawRecord:
        """
        从爬虫行数据创建原始岗位记录。

        Args:
            db: 数据库会话。
            crawl_run_id: 本次爬虫运行记录 ID。
            platform: 招聘平台标识。
            row: 单条爬虫岗位数据。

        Returns:
            已保存的原始岗位记录。
        """
        raw_json = self.parser_service.parse_raw_json(row)
        collected_at = self.parser_service.parse_datetime(row.get("collected_at")) or datetime.now()
        raw_record = JobRawRecord(
            crawl_run_id=crawl_run_id,
            platform=platform,
            platform_job_id=self.parser_service.to_optional_str(row.get("job_id")),
            source_url=self.parser_service.to_optional_str(row.get("job_url")),
            raw_title=self.parser_service.to_optional_str(row.get("job_title_raw")),
            raw_company_name=self.parser_service.to_optional_str(row.get("company_name")),
            raw_city=self.parser_service.to_optional_str(row.get("city")),
            job_description=self.parser_service.to_optional_str(row.get("job_description")),
            raw_json=raw_json,
            content_hash=self.parser_service.build_content_hash(platform, row, raw_json),
            collected_at=collected_at,
        )
        return self.repository.create_raw_record(raw_record, db)

    def upsert_posting_from_raw_record(
        self,
        db: Session,
        raw_record: JobRawRecord,
        row: dict[str, Any],
    ) -> tuple[JobPosting | None, bool]:
        """
        根据原始岗位记录新增或更新岗位主表。

        Args:
            db: 数据库会话。
            raw_record: 已保存的原始岗位记录。
            row: 单条爬虫岗位数据。

        Returns:
            岗位主表记录，以及是否为新建记录。
        """
        existing = self.repository.find_posting_for_upsert(
            raw_record.platform,
            raw_record.platform_job_id,
            raw_record.source_url,
            db,
        )
        salary_min, salary_max = self.parser_service.parse_salary_range(row.get("salary_text"))
        experience_min, experience_max = self.parser_service.parse_experience_range(row.get("experience_text"))
        published_at = self.parser_service.parse_datetime(row.get("published_at"))
        now = datetime.now()

        if existing:
            # 已存在的岗位只更新会变化的字段，并刷新 last_seen_at 表示最近一次仍然采集到。
            existing.source_url = raw_record.source_url or existing.source_url
            existing.job_title_raw = raw_record.raw_title or existing.job_title_raw
            existing.company_name = raw_record.raw_company_name or existing.company_name
            existing.city = raw_record.raw_city or existing.city
            existing.location = self.parser_service.to_optional_str(row.get("location")) or existing.location
            existing.salary_text = self.parser_service.to_optional_str(row.get("salary_text")) or existing.salary_text
            existing.salary_min_k = salary_min or existing.salary_min_k
            existing.salary_max_k = salary_max or existing.salary_max_k
            existing.experience_text = self.parser_service.to_optional_str(row.get("experience_text")) or existing.experience_text
            existing.experience_min_years = experience_min or existing.experience_min_years
            existing.experience_max_years = experience_max or existing.experience_max_years
            existing.education_text = self.parser_service.to_optional_str(row.get("education_text")) or existing.education_text
            existing.employment_type = self.parser_service.to_optional_str(row.get("employment_type")) or existing.employment_type
            existing.industry = self.parser_service.to_optional_str(row.get("industry")) or existing.industry
            existing.company_size = self.parser_service.to_optional_str(row.get("company_size")) or existing.company_size
            existing.job_description = raw_record.job_description or existing.job_description
            existing.published_at = published_at or existing.published_at
            existing.last_seen_at = raw_record.collected_at
            existing.status = JOB_STATUS_RECRUITING
            existing.raw_record_id = raw_record.id
            existing.updated_at = now
            return self.repository.save_posting(existing, db), False

        posting = JobPosting(
            platform=raw_record.platform,
            platform_job_id=raw_record.platform_job_id,
            source_url=raw_record.source_url,
            job_title_raw=raw_record.raw_title,
            job_title_standard=raw_record.raw_title,
            company_name=raw_record.raw_company_name,
            city=raw_record.raw_city,
            location=self.parser_service.to_optional_str(row.get("location")),
            salary_text=self.parser_service.to_optional_str(row.get("salary_text")),
            salary_min_k=salary_min,
            salary_max_k=salary_max,
            experience_text=self.parser_service.to_optional_str(row.get("experience_text")),
            experience_min_years=experience_min,
            experience_max_years=experience_max,
            education_text=self.parser_service.to_optional_str(row.get("education_text")),
            employment_type=self.parser_service.to_optional_str(row.get("employment_type")),
            industry=self.parser_service.to_optional_str(row.get("industry")),
            company_size=self.parser_service.to_optional_str(row.get("company_size")),
            job_description=raw_record.job_description,
            published_at=published_at,
            first_seen_at=raw_record.collected_at,
            last_seen_at=raw_record.collected_at,
            status=JOB_STATUS_RECRUITING,
            raw_record_id=raw_record.id,
        )
        return self.repository.save_posting(posting, db), True
