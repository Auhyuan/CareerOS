import hashlib
import json
from datetime import datetime
from typing import Any

from sqlmodel import Session

from app.server.job.src.clients import CapabilitySpiderClient
from app.server.job.src.config.job_config import (
    SPIDER_RUN_STATUS_FAILED,
    SPIDER_RUN_STATUS_RUNNING,
    SPIDER_RUN_STATUS_SUCCESS,
)
from app.server.job.src.models.job_model import JobRawRecord, SpiderCrawlRun
from app.server.job.src.repository.job_repository import JobRepository


class JobCrawlService:
    """岗位采集编排服务，负责调用能力层爬虫并把结果写入原始岗位池。"""

    def __init__(
        self,
        capability_spider_client: CapabilitySpiderClient | None = None,
        repository: JobRepository | None = None,
    ):
        """
        初始化岗位采集编排服务。
        Args:
            capability_spider_client: 能力层爬虫接口客户端。
            repository: 岗位库数据访问对象。
        """
        self.capability_spider_client = capability_spider_client or CapabilitySpiderClient()
        self.repository = repository or JobRepository()

    def crawl_qcwy_jobs_and_ingest(self, db: Session, request: Any) -> dict[str, Any]:
        """
        编排前程无忧岗位采集和原始岗位入库流程。
        Args:
            db: 数据库会话。
            request: 前程无忧岗位采集并入库请求。
        Returns:
            包含采集结果、爬虫运行记录 ID 和入库统计的响应字典。
        """
        crawl_run_id: int | None = None
        ingest_stats: dict[str, int] | None = None

        if request.persist_to_db:
            crawl_run = self._create_crawl_run(db, request)
            crawl_run_id = crawl_run.id

        try:
            # 入库必须使用完整 rows，所以调用能力层时强制 fields 为空；
            # 返回给调用方前再根据原始 request.fields 做字段裁剪。
            capability_payload = request.model_dump(mode="json")
            capability_payload.pop("persist_to_db", None)
            capability_payload["fields"] = []

            crawl_result = self.capability_spider_client.crawl_qcwy_jobs(capability_payload)
            rows = crawl_result.get("rows") or []

            if request.persist_to_db and crawl_run_id is not None:
                ingest_stats = self._ingest_raw_records(
                    db,
                    crawl_run_id=crawl_run_id,
                    platform="qcwy",
                    rows=rows,
                )
                self._mark_crawl_run_success(db, crawl_run_id, len(rows))

            return_rows = self._filter_return_fields(rows, request.fields) if request.fields else rows
            return {
                "platform": crawl_result.get("platform", "qcwy"),
                "total": len(return_rows),
                "rows": return_rows,
                "csv_path": crawl_result.get("csv_path"),
                "excel_path": crawl_result.get("excel_path"),
                "crawl_run_id": crawl_run_id,
                "ingest_stats": ingest_stats,
            }
        except Exception as error:
            if request.persist_to_db and crawl_run_id is not None:
                self._mark_crawl_run_failed(db, crawl_run_id, str(error))
            raise

    def _create_crawl_run(self, db: Session, request: Any) -> SpiderCrawlRun:
        """
        创建爬虫运行记录。
        Args:
            db: 数据库会话。
            request: 采集请求对象。
        Returns:
            已保存的爬虫运行记录。
        """
        crawl_run = SpiderCrawlRun(
            platform="qcwy",
            keyword=",".join(request.keywords),
            city=",".join(request.cities),
            pages=request.pages,
            status=SPIDER_RUN_STATUS_RUNNING,
            total_count=0,
            request_params=request.model_dump(mode="json"),
            started_at=datetime.now(),
        )
        return self.repository.create_crawl_run(crawl_run, db)

    def _mark_crawl_run_success(self, db: Session, crawl_run_id: int, total_count: int) -> None:
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

    def _mark_crawl_run_failed(self, db: Session, crawl_run_id: int, error_message: str) -> None:
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

    def _ingest_raw_records(
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
            原始岗位入库统计信息。
        """
        raw_created = 0
        for row in rows:
            self._create_raw_record_from_row(db, crawl_run_id, platform, row)
            raw_created += 1
        return {"raw_created": raw_created}

    def _create_raw_record_from_row(
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
        raw_json = self._parse_raw_json(row)
        collected_at = self._parse_datetime(row.get("collected_at")) or datetime.now()

        # 原始岗位表只抽取少量通用检索字段，完整平台字段全部保存在 raw_json 中。
        raw_record = JobRawRecord(
            crawl_run_id=crawl_run_id,
            platform=platform,
            platform_job_id=self._to_optional_str(row.get("job_id")),
            source_url=self._to_optional_str(row.get("job_url")),
            raw_title=self._to_optional_str(row.get("job_title_raw")),
            raw_company_name=self._to_optional_str(row.get("company_name")),
            raw_city=self._to_optional_str(row.get("city")),
            job_description=self._to_optional_str(row.get("job_description")),
            raw_json=raw_json,
            content_hash=self._build_content_hash(platform, row, raw_json),
            collected_at=collected_at,
        )
        return self.repository.create_raw_record(raw_record, db)

    def _parse_raw_json(self, row: dict[str, Any]) -> dict[str, Any]:
        """
        从爬虫行数据中解析 raw_json 字段。
        Args:
            row: 单条爬虫岗位数据。
        Returns:
            可写入 JSONB 字段的原始数据字典。
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

    def _build_content_hash(self, platform: str, row: dict[str, Any], raw_json: dict[str, Any]) -> str:
        """
        构造岗位内容哈希，用于原始记录去重和后续排查。
        Args:
            platform: 招聘平台标识。
            row: 单条爬虫岗位数据。
            raw_json: 解析后的原始 JSON。
        Returns:
            SHA256 内容哈希。
        """
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

    def _parse_datetime(self, value: Any) -> datetime | None:
        """
        尽量把字符串时间解析成 datetime。
        Args:
            value: 原始时间值。
        Returns:
            datetime 对象；无法解析时返回 None。
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

    def _to_optional_str(self, value: Any) -> str | None:
        """
        把任意值转换成可选字符串，空字符串会转为 None。
        Args:
            value: 任意字段值。
        Returns:
            清理后的字符串或 None。
        """
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _filter_return_fields(self, rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
        """
        按调用方指定字段裁剪 API 返回数据。
        Args:
            rows: 完整岗位数据列表。
            fields: 调用方需要返回的字段名列表。
        Returns:
            已裁剪字段的岗位数据列表。
        """
        return [{field: row.get(field) for field in fields} for row in rows]
