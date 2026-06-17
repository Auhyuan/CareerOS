from typing import Any

from sqlmodel import Session

from app.server.job.src.clients import CapabilitySpiderClient
from app.server.job.src.service.job_ingest_service import JobIngestService


class JobCrawlService:
    """岗位采集编排服务，负责调用能力层爬虫并把结果交给入库服务。"""

    def __init__(
        self,
        capability_spider_client: CapabilitySpiderClient | None = None,
        ingest_service: JobIngestService | None = None,
    ):
        """
        初始化岗位采集编排服务。

        Args:
            capability_spider_client: 能力层爬虫客户端。
            ingest_service: 岗位采集结果入库服务。
        """
        self.capability_spider_client = capability_spider_client or CapabilitySpiderClient()
        self.ingest_service = ingest_service or JobIngestService()

    def crawl_qcwy_jobs_and_ingest(self, db: Session, request: Any) -> dict[str, Any]:
        """
        编排前程无忧岗位采集和入库流程。

        Args:
            db: 数据库会话。
            request: 前程无忧岗位采集并入库请求。

        Returns:
            包含采集结果、爬虫运行记录 ID 和入库统计的响应字典。
        """
        crawl_run_id: int | None = None
        ingest_stats: dict[str, int] | None = None

        if request.persist_to_db:
            crawl_run = self.ingest_service.create_crawl_run(
                db,
                platform="qcwy",
                keywords=request.keywords,
                cities=request.cities,
                pages=request.pages,
                request_params=request.model_dump(mode="json"),
            )
            crawl_run_id = crawl_run.id

        try:
            # 入库必须使用完整 rows，因此调用能力层时强制 fields 为空；返回给调用方前再裁剪字段。
            capability_payload = request.model_dump(mode="json")
            capability_payload.pop("persist_to_db", None)
            capability_payload["fields"] = []

            crawl_result = self.capability_spider_client.crawl_qcwy_jobs(capability_payload)
            rows = crawl_result.get("rows") or []

            if request.persist_to_db and crawl_run_id is not None:
                ingest_stats = self.ingest_service.ingest_spider_rows(
                    db,
                    crawl_run_id=crawl_run_id,
                    platform="qcwy",
                    rows=rows,
                )
                self.ingest_service.mark_crawl_run_success(db, crawl_run_id, len(rows))

            return_rows = self.filter_return_fields(rows, request.fields) if request.fields else rows
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
                self.ingest_service.mark_crawl_run_failed(db, crawl_run_id, str(error))
            raise

    def filter_return_fields(self, rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
        """
        按调用方指定字段裁剪 API 返回数据。

        Args:
            rows: 完整岗位数据列表。
            fields: 调用方需要返回的字段名列表。

        Returns:
            已裁剪字段的岗位数据列表。
        """
        return [{field: row.get(field) for field in fields} for row in rows]
