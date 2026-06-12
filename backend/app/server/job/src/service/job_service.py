import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session

from app.server.job.src.config.job_config import (
    JOB_DEFAULT_PAGE,
    JOB_DEFAULT_PAGE_SIZE,
    JOB_MAX_PAGE_SIZE,
    JOB_STATUS_RECRUITING,
    SPIDER_RUN_STATUS_FAILED,
    SPIDER_RUN_STATUS_RUNNING,
    SPIDER_RUN_STATUS_SUCCESS,
)
from app.server.job.src.models.job_model import (
    JobDirection,
    JobMarketProfile,
    JobPosting,
    JobRawRecord,
    SpiderCrawlRun,
)
from app.server.job.src.repository.job_repository import JobRepository


class JobService:
    """岗位库业务服务层。"""

    def __init__(self, repository: JobRepository | None = None):
        """
        初始化岗位库服务。

        Args:
            repository: 岗位库数据访问对象，默认创建 JobRepository。
        """
        self.repository = repository or JobRepository()

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
        """
        raw_json = self.parse_raw_json(row)
        collected_at = self.parse_datetime(row.get("collected_at")) or datetime.now()
        raw_record = JobRawRecord(
            crawl_run_id=crawl_run_id,
            platform=platform,
            platform_job_id=self.to_optional_str(row.get("job_id")),
            source_url=self.to_optional_str(row.get("job_url")),
            raw_title=self.to_optional_str(row.get("job_title_raw")),
            raw_company_name=self.to_optional_str(row.get("company_name")),
            raw_city=self.to_optional_str(row.get("city")),
            job_description=self.to_optional_str(row.get("job_description")),
            raw_json=raw_json,
            content_hash=self.build_content_hash(platform, row, raw_json),
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
        """
        existing = self.repository.find_posting_for_upsert(
            raw_record.platform,
            raw_record.platform_job_id,
            raw_record.source_url,
            db,
        )
        salary_min, salary_max = self.parse_salary_range(row.get("salary_text"))
        experience_min, experience_max = self.parse_experience_range(row.get("experience_text"))
        published_at = self.parse_datetime(row.get("published_at"))
        now = datetime.now()

        if existing:
            # 已存在的岗位只更新会变化的字段，并刷新 last_seen_at，表示最近一次仍然采集到。
            existing.source_url = raw_record.source_url or existing.source_url
            existing.job_title_raw = raw_record.raw_title or existing.job_title_raw
            existing.company_name = raw_record.raw_company_name or existing.company_name
            existing.city = raw_record.raw_city or existing.city
            existing.location = self.to_optional_str(row.get("location")) or existing.location
            existing.salary_text = self.to_optional_str(row.get("salary_text")) or existing.salary_text
            existing.salary_min_k = salary_min or existing.salary_min_k
            existing.salary_max_k = salary_max or existing.salary_max_k
            existing.experience_text = self.to_optional_str(row.get("experience_text")) or existing.experience_text
            existing.experience_min_years = experience_min or existing.experience_min_years
            existing.experience_max_years = experience_max or existing.experience_max_years
            existing.education_text = self.to_optional_str(row.get("education_text")) or existing.education_text
            existing.employment_type = self.to_optional_str(row.get("employment_type")) or existing.employment_type
            existing.industry = self.to_optional_str(row.get("industry")) or existing.industry
            existing.company_size = self.to_optional_str(row.get("company_size")) or existing.company_size
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
            location=self.to_optional_str(row.get("location")),
            salary_text=self.to_optional_str(row.get("salary_text")),
            salary_min_k=salary_min,
            salary_max_k=salary_max,
            experience_text=self.to_optional_str(row.get("experience_text")),
            experience_min_years=experience_min,
            experience_max_years=experience_max,
            education_text=self.to_optional_str(row.get("education_text")),
            employment_type=self.to_optional_str(row.get("employment_type")),
            industry=self.to_optional_str(row.get("industry")),
            company_size=self.to_optional_str(row.get("company_size")),
            job_description=raw_record.job_description,
            published_at=published_at,
            first_seen_at=raw_record.collected_at,
            last_seen_at=raw_record.collected_at,
            status=JOB_STATUS_RECRUITING,
            raw_record_id=raw_record.id,
        )
        return self.repository.save_posting(posting, db), True

    def list_postings(
        self,
        db: Session,
        *,
        keyword: str | None = None,
        city: str | None = None,
        platform: str | None = None,
        status: str | None = None,
        page: int = JOB_DEFAULT_PAGE,
        page_size: int = JOB_DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        """
        分页查询岗位库。

        Args:
            db: 数据库会话。
            keyword: 岗位标题关键词。
            city: 城市筛选。
            platform: 平台筛选。
            status: 岗位状态筛选。
            page: 页码。
            page_size: 每页数量。
        """
        safe_page = max(page, 1)
        safe_page_size = min(max(page_size, 1), JOB_MAX_PAGE_SIZE)
        rows, total = self.repository.list_postings(
            db,
            keyword=keyword,
            city=city,
            platform=platform,
            status=status,
            page=safe_page,
            page_size=safe_page_size,
        )
        return {
            "items": rows,
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
        }

    def get_posting_detail(self, db: Session, job_id: int) -> JobPosting | None:
        """
        查询岗位详情。

        Args:
            db: 数据库会话。
            job_id: 岗位主表 ID。
        """
        return self.repository.get_posting_by_id(job_id, db)

    def list_raw_records_by_job(self, db: Session, job_id: int, limit: int = 20) -> list[JobRawRecord]:
        """
        查询某个岗位最近的原始采集记录。

        Args:
            db: 数据库会话。
            job_id: 岗位主表 ID。
            limit: 返回数量上限。
        """
        job = self.repository.get_posting_by_id(job_id, db)
        if job is None:
            return []
        return self.repository.list_raw_records_by_job(job, db, limit=limit)

    def list_directions(
        self,
        db: Session,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = JOB_DEFAULT_PAGE,
        page_size: int = JOB_DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        """
        分页查询平台岗位方向。

        Args:
            db: 数据库会话。
            keyword: 岗位方向关键词。
            status: 岗位方向状态。
            page: 页码。
            page_size: 每页数量。
        """
        safe_page = max(page, 1)
        safe_page_size = min(max(page_size, 1), JOB_MAX_PAGE_SIZE)
        rows, total = self.repository.list_directions(
            db,
            keyword=keyword,
            status=status,
            page=safe_page,
            page_size=safe_page_size,
        )
        return {
            "items": rows,
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
        }

    def get_direction_detail(self, db: Session, direction_id: int) -> JobDirection | None:
        """
        查询岗位方向详情。

        Args:
            db: 数据库会话。
            direction_id: 岗位方向 ID。
        """
        return self.repository.get_direction_by_id(direction_id, db)

    def get_profile_by_direction_id(self, db: Session, direction_id: int) -> JobMarketProfile | None:
        """
        查询某个岗位方向的聚合画像。

        Args:
            db: 数据库会话。
            direction_id: 岗位方向 ID。
        """
        return self.repository.get_profile_by_direction_id(direction_id, db)

    def parse_raw_json(self, row: dict[str, Any]) -> dict[str, Any]:
        """
        从爬虫行中解析 raw_json 字段。

        Args:
            row: 单条爬虫岗位数据。
        """
        raw_json_value = row.get("raw_json")
        if isinstance(raw_json_value, dict):
            return raw_json_value
        if isinstance(raw_json_value, str) and raw_json_value.strip():
            try:
                return json.loads(raw_json_value)
            except json.JSONDecodeError:
                return {"raw_json_text": raw_json_value}
        return dict(row)

    def build_content_hash(self, platform: str, row: dict[str, Any], raw_json: dict[str, Any]) -> str:
        """
        构造岗位内容哈希，用于原始记录去重和后续排查。

        Args:
            platform: 招聘平台标识。
            row: 单条爬虫岗位数据。
            raw_json: 解析后的原始 JSON。
        """
        # 哈希尽量使用稳定字段；没有平台 ID 时再退回到原始 JSON。
        stable_payload = {
            "platform": platform,
            "job_id": row.get("job_id"),
            "job_url": row.get("job_url"),
            "job_title_raw": row.get("job_title_raw"),
            "company_name": row.get("company_name"),
            "job_description": row.get("job_description"),
            "raw_json": raw_json,
        }
        text = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def parse_salary_range(self, salary_text: Any) -> tuple[Decimal | None, Decimal | None]:
        """
        从薪资文本中尽量解析出 K/月维度的最小值和最大值。

        Args:
            salary_text: 原始薪资文本，例如 10-15K、1-1.5万、8千-1.2万。
        """
        text = str(salary_text or "").upper().replace(" ", "")
        if not text or any(word in text for word in ["面议", "薪资面议"]):
            return None, None

        # 前程无忧常见薪资单位是 千、万、K；这里按月薪 K 做第一版归一化。
        token_pattern = re.compile(r"(\d+(?:\.\d+)?)(万|千|K)?")
        values: list[Decimal] = []
        for number, unit in token_pattern.findall(text):
            value = Decimal(number)
            if unit == "万":
                value *= Decimal("10")
            elif unit in {"千", "K", ""}:
                value = value
            values.append(value)

        if not values:
            return None, None
        if len(values) == 1:
            return values[0], values[0]
        return min(values), max(values)

    def parse_experience_range(self, experience_text: Any) -> tuple[Decimal | None, Decimal | None]:
        """
        从经验文本中解析最小年限和最大年限。

        Args:
            experience_text: 原始经验文本，例如 1-3年、3年以上、经验不限。
        """
        text = str(experience_text or "").replace(" ", "")
        if not text:
            return None, None
        if any(word in text for word in ["不限", "无需", "应届", "在校"]):
            return Decimal("0"), Decimal("0")

        numbers = [Decimal(item) for item in re.findall(r"\d+(?:\.\d+)?", text)]
        if not numbers:
            return None, None
        if len(numbers) == 1:
            if any(word in text for word in ["以上", "+"]):
                return numbers[0], None
            return numbers[0], numbers[0]
        return min(numbers), max(numbers)

    def parse_datetime(self, value: Any) -> datetime | None:
        """
        尽量把字符串时间解析成 datetime。

        Args:
            value: 原始时间值。
        """
        if isinstance(value, datetime):
            return value
        if not value:
            return None

        text = str(value).strip()
        known_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
        ]
        for date_format in known_formats:
            try:
                return datetime.strptime(text, date_format)
            except ValueError:
                continue
        return None

    def to_optional_str(self, value: Any) -> str | None:
        """
        把任意值转换成可选字符串，空字符串会转为 None。

        Args:
            value: 任意字段值。
        """
        if value is None:
            return None
        text = str(value).strip()
        return text or None
