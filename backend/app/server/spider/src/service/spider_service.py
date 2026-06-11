from app.server.spider.src.providers.qcwy.provider import QcwyProvider
from app.server.spider.src.schemas.request import QcwyJobCrawlRequest


class SpiderService:
    """爬虫服务业务编排层。"""

    def __init__(self, qcwy_provider: QcwyProvider | None = None):
        """
        初始化爬虫服务。

        Args:
            qcwy_provider: 前程无忧采集 provider，默认创建 QcwyProvider
        """
        self.qcwy_provider = qcwy_provider or QcwyProvider()

    def crawl_qcwy_jobs(self, request: QcwyJobCrawlRequest):
        """
        执行前程无忧岗位采集任务。

        Args:
            request: 前程无忧岗位采集请求参数
        """
        return self.qcwy_provider.crawl_jobs(request)
