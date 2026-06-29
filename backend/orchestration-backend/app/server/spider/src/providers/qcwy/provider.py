from app.server.spider.src.config.spider_config import QCWY_DEFAULT_OUTPUT_DIR, QCWY_DEFAULT_PROFILE_DIR
from app.server.spider.src.providers.qcwy.crawler.qcwy_spider.browser_spider import QcwyBrowserSpider
from app.server.spider.src.providers.qcwy.crawler.qcwy_spider.config import SpiderConfig
from app.server.spider.src.providers.qcwy.crawler.qcwy_spider.spider import QcwySpider
from app.server.spider.src.schemas.request import QcwyJobCrawlRequest


class QcwyProvider:
    """前程无忧采集器适配层。"""

    def crawl_jobs(self, request: QcwyJobCrawlRequest):
        """
        根据 API 请求参数执行前程无忧岗位采集。

        Args:
            request: 前程无忧岗位采集请求参数。
        """
        # 将接口层的 Pydantic 请求模型转换成底层爬虫的运行配置。
        # Provider 只做采集参数编排，不处理入库、字段裁剪等上层业务逻辑。
        config = SpiderConfig(
            fetch_mode=request.fetch_mode,
            keywords=request.keywords,
            cities=request.cities,
            max_pages=request.pages,
            page_size=request.page_size,
            request_delay_seconds=2,
            output_dir=QCWY_DEFAULT_OUTPUT_DIR,
            save_raw_json=request.save_raw_json,
            save_csv=request.save_csv,
            save_excel=request.save_excel,
            timeout_seconds=20,
            cookie="",
            browser_headless=request.browser_headless,
            browser_user_data_dir=QCWY_DEFAULT_PROFILE_DIR,
            browser_wait_seconds=request.browser_wait_seconds,
            browser_executable_path=request.browser_executable_path,
            browser_disable_no_sandbox=True,
        )

        # 当前前程无忧页面更适合使用 browser 模式；requests 模式先保留为轻量备用方案。
        spider = QcwyBrowserSpider(config) if request.fetch_mode == "browser" else QcwySpider(config)
        result = spider.run()

        return {
            "platform": "前程无忧",
            "total": len(result["rows"]),
            "rows": result["rows"],
            "csv_path": result["csv_path"],
            "excel_path": result["excel_path"],
        }
