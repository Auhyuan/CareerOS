import logging


def configure_logging() -> None:
    """初始化 Hai-agent 的基础日志格式。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
