from typing import Any

from app.server.spider.src.providers.qcwy.provider import QcwyProvider
from app.server.spider.src.schemas.request import QcwyJobCrawlRequest


class SpiderService:
    """爬虫能力服务层，只负责执行采集并返回结果。"""

    def __init__(self, qcwy_provider: QcwyProvider | None = None):
        """
        初始化爬虫能力服务。

        Args:
            qcwy_provider: 前程无忧采集 provider；默认创建 QcwyProvider。
        """
        self.qcwy_provider = qcwy_provider or QcwyProvider()

    def crawl_qcwy_jobs(self, request: QcwyJobCrawlRequest) -> dict[str, Any]:
        """
        执行前程无忧岗位采集任务。

        能力层不接收数据库会话，也不写入岗位库。入库、去重、标准化和任务记录由编排层负责。

        Args:
            request: 前程无忧岗位采集请求参数。

        Returns:
            采集结果字典；如果 request.fields 不为空，则只裁剪接口返回字段。
        """
        result = self.qcwy_provider.crawl_jobs(request)
        rows = result["rows"]

        # 字段裁剪只影响 API 返回，不影响 provider 内部采集过程。
        if request.fields:
            rows = self.filter_return_fields(rows, request.fields)

        return {
            **result,
            "rows": rows,
            "total": len(rows),
        }

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
