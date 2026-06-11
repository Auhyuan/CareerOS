try:
    from .qcwy_spider.browser_spider import QcwyBrowserSpider
    from .qcwy_spider.config import SpiderConfig
    from .qcwy_spider.spider import QcwySpider
except ImportError:
    from qcwy_spider.browser_spider import QcwyBrowserSpider
    from qcwy_spider.config import SpiderConfig
    from qcwy_spider.spider import QcwySpider


def main():
    """创建配置和爬虫实例，并启动一次前程无忧岗位采集任务。"""
    config = SpiderConfig.from_cli()
    if config.fetch_mode == "browser":
        spider = QcwyBrowserSpider(config)
    else:
        spider = QcwySpider(config)
    spider.run()


if __name__ == "__main__":
    main()
