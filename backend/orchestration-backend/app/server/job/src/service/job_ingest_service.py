from datetime import datetime
from typing import Any

from sqlmodel import Session

from app.server.job.src.config.job_config import (
    SPIDER_RUN_STATUS_FAILED,
    SPIDER_RUN_STATUS_RUNNING,
    SPIDER_RUN_STATUS_SUCCESS,
)
from app.server.job.src.models.job_model import JobRawRecord, SpiderCrawlRun
from app.server.job.src.repository.job_repository import JobRepository
from app.server.job.src.service.job_parser_service import JobParserService


class JobIngestService:
    """岗位采集结果入库服务，只负责爬虫任务和原始岗位记录写入。"""

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
            keywords: 本次采集关键字列表。
            cities: 本次采集城市列表。
            pages: 每组关键字和城市采集页数。
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
        把爬虫采集结果写入原始岗位表。
        Args:
            db: 数据库会话。
            crawl_run_id: 本次爬虫运行记录 ID。
            platform: 招聘平台标识，例如 qcwy。
            rows: 爬虫返回的岗位行列表。
        Returns:
            入库统计信息。
        """
        raw_created = 0

        for row in rows:
            self.create_raw_record_from_row(db, crawl_run_id, platform, row)
            raw_created += 1

        return {"raw_created": raw_created}

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

        # 原始岗位表只抽取少量通用检索字段，完整平台字段全部保存在 raw_json 中。
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
