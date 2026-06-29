import hashlib
import json
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
from app.server.spider.src.schemas.request import QcwyJobCrawlRequest
from app.server.spider.src.service.spider_service import SpiderService


class JobCrawlService:
    """Job crawl orchestration service.

    This service owns the business flow around crawling: creating crawl-run records,
    running the local spider module, ingesting raw rows, and returning caller-facing rows.
    """

    def __init__(
        self,
        spider_service: SpiderService | None = None,
        repository: JobRepository | None = None,
    ):
        """Initialize the job crawl orchestration service.

        Args:
            spider_service: Local spider service. A default SpiderService is created when omitted.
            repository: Job repository used to persist crawl runs and raw records.
        """
        self.spider_service = spider_service or SpiderService()
        self.repository = repository or JobRepository()

    def crawl_qcwy_jobs_and_ingest(self, db: Session, request: Any) -> dict[str, Any]:
        """Run QCWY crawling and optionally ingest raw job records.

        Args:
            db: Database session.
            request: QCWY crawl-and-ingest request from the Job API layer.

        Returns:
            Crawl result, optional crawl_run_id, and optional ingest statistics.
        """
        crawl_run_id: int | None = None
        ingest_stats: dict[str, int] | None = None

        if request.persist_to_db:
            crawl_run = self._create_crawl_run(db, request)
            crawl_run_id = crawl_run.id

        try:
            # Ingestion needs complete rows, so the local spider is called with fields=[] first.
            # The public response is filtered later according to the original request.fields.
            spider_payload = request.model_dump(mode="json")
            spider_payload.pop("persist_to_db", None)
            spider_payload["fields"] = []
            spider_request = QcwyJobCrawlRequest.model_validate(spider_payload)

            crawl_result = self.spider_service.crawl_qcwy_jobs(spider_request)
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
        """Create a crawl-run record before the spider starts.

        Args:
            db: Database session.
            request: Crawl request object.

        Returns:
            Persisted SpiderCrawlRun model.
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
        """Mark a crawl-run record as successful.

        Args:
            db: Database session.
            crawl_run_id: Crawl-run record ID.
            total_count: Number of crawled raw rows.
        """
        self.repository.update_crawl_run(
            crawl_run_id,
            db,
            status=SPIDER_RUN_STATUS_SUCCESS,
            total_count=total_count,
            finished_at=datetime.now(),
        )

    def _mark_crawl_run_failed(self, db: Session, crawl_run_id: int, error_message: str) -> None:
        """Mark a crawl-run record as failed.

        Args:
            db: Database session.
            crawl_run_id: Crawl-run record ID.
            error_message: Failure reason.
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
        """Persist spider rows into the raw job record table.

        Args:
            db: Database session.
            crawl_run_id: Current crawl-run record ID.
            platform: Recruitment platform code, such as qcwy.
            rows: Spider result rows.

        Returns:
            Ingestion statistics.
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
        """Create one raw job record from one spider row.

        Args:
            db: Database session.
            crawl_run_id: Current crawl-run record ID.
            platform: Recruitment platform code.
            row: One spider result row.

        Returns:
            Persisted JobRawRecord model.
        """
        raw_json = self._parse_raw_json(row)
        collected_at = self._parse_datetime(row.get("collected_at")) or datetime.now()

        # Keep complete platform-specific data in raw_json while extracting only common searchable fields.
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
        """Parse the row raw_json field into a JSONB-compatible dict.

        Args:
            row: One spider result row.

        Returns:
            Parsed raw JSON dictionary.
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
        """Build a stable content hash for deduplication and troubleshooting.

        Args:
            platform: Recruitment platform code.
            row: One spider result row.
            raw_json: Parsed raw JSON payload.

        Returns:
            SHA256 content hash.
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
        """Best-effort parse a raw datetime value.

        Args:
            value: Raw datetime value.

        Returns:
            Parsed datetime, or None when parsing fails.
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
        """Convert a raw value into an optional stripped string.

        Args:
            value: Raw field value.

        Returns:
            Stripped string, or None for empty values.
        """
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _filter_return_fields(self, rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
        """Filter API response rows by caller-selected fields.

        Args:
            rows: Complete job rows.
            fields: Field names requested by the caller.

        Returns:
            Rows containing only selected fields.
        """
        return [{field: row.get(field) for field in fields} for row in rows]
