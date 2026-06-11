from app.server.spider.src.QCWY.qcwy_spider.browser_spider import QcwyBrowserSpider
from app.server.spider.src.QCWY.qcwy_spider.config import SpiderConfig, env_str, load_env
from app.server.spider.src.QCWY.qcwy_spider.spider import QcwySpider
from app.server.spider.src.config.spider_config import QCWY_DEFAULT_OUTPUT_DIR, QCWY_DEFAULT_PROFILE_DIR
from app.server.spider.src.schemas.request import QcwyJobCrawlRequest


class QcwyProvider:
    """前程无忧采集器适配层。"""

    def crawl_jobs(self, request: QcwyJobCrawlRequest):
        """
        根据 API 请求参数执行前程无忧岗位采集。

        Args:
            request: 前程无忧岗位采集请求参数
        """
        # 加载 QCWY/.env，允许 API 请求省略本机浏览器路径等运行配置。
        load_env()

        # 将 API 层的 Pydantic 请求模型转换为现有 QCWY 爬虫的配置对象。
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
            browser_executable_path=request.browser_executable_path or env_str("QCWY_BROWSER_EXECUTABLE_PATH", ""),
            browser_disable_no_sandbox=True,
        )

        # browser 模式更适合前程无忧当前页面；requests 模式保留为轻量备用。
        spider = QcwyBrowserSpider(config) if request.fetch_mode == "browser" else QcwySpider(config)
        result = spider.run()
        rows = result["rows"]

        # fields 用于控制 API 返回字段，爬虫仍然保留完整原始数据用于落盘和后续清洗。
        if request.fields:
            rows = [{field: row.get(field) for field in request.fields} for row in rows]

        return {
            "platform": "前程无忧",
            "total": len(rows),
            "rows": rows,
            "csv_path": result["csv_path"],
            "excel_path": result["excel_path"],
        }
