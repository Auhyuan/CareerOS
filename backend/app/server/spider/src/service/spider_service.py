from typing import Any

from sqlmodel import Session

from app.server.job.src.service.job_service import JobService
from app.server.spider.src.providers.qcwy.provider import QcwyProvider
from app.server.spider.src.schemas.request import QcwyJobCrawlRequest


class SpiderService:
    """爬虫服务业务编排层。"""

    def __init__(
        self,
        qcwy_provider: QcwyProvider | None = None,
        job_service: JobService | None = None,
    ):
        """
        初始化爬虫服务。

        Args:
            qcwy_provider: 前程无忧采集 provider；默认创建 QcwyProvider。
            job_service: 岗位库服务；默认创建 JobService。
        """
        self.qcwy_provider = qcwy_provider or QcwyProvider()
        self.job_service = job_service or JobService()

    def crawl_qcwy_jobs(self, request: QcwyJobCrawlRequest, db: Session | None = None) -> dict[str, Any]:
        """
        执行前程无忧岗位采集任务，并按需写入岗位库。

        Args:
            request: 前程无忧岗位采集请求参数。
            db: 数据库会话；当 persist_to_db 为 True 时需要传入。
        """
        crawl_run_id: int | None = None
        if request.persist_to_db and db is not None:
            crawl_run = self.job_service.create_crawl_run(
                db,
                platform="qcwy",
                keywords=request.keywords,
                cities=request.cities,
                pages=request.pages,
                request_params=request.model_dump(mode="json"),
            )
            crawl_run_id = crawl_run.id

        try:
            result = self.qcwy_provider.crawl_jobs(request)
            rows = result["rows"]
            ingest_stats = None

            if request.persist_to_db and db is not None and crawl_run_id is not None:
                # 入库必须使用完整 rows，所以字段裁剪在入库之后执行。
                ingest_stats = self.job_service.ingest_spider_rows(
                    db,
                    crawl_run_id=crawl_run_id,
                    platform="qcwy",
                    rows=rows,
                )
                self.job_service.mark_crawl_run_success(db, crawl_run_id, len(rows))

            if request.fields:
                rows = self.filter_return_fields(rows, request.fields)

            return {
                **result,
                "rows": rows,
                "total": len(rows),
                "crawl_run_id": crawl_run_id,
                "ingest_stats": ingest_stats,
            }
        except Exception as error:
            if request.persist_to_db and db is not None and crawl_run_id is not None:
                self.job_service.mark_crawl_run_failed(db, crawl_run_id, str(error))
            raise

    def filter_return_fields(self, rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
        """
        按调用方指定字段裁剪 API 返回数据。

        Args:
            rows: 完整岗位数据列表。
            fields: 调用方需要返回的字段名列表。
        """
        return [{field: row.get(field) for field in fields} for row in rows]
