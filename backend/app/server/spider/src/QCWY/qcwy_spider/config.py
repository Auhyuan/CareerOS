import argparse
import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"


def load_env(env_path=ENV_PATH):
    """读取项目根目录下的 .env 文件，并写入环境变量。"""
    if not env_path.exists():
        return

    # 这里不用 python-dotenv，减少依赖；只支持 KEY=VALUE 这种简单配置。
    with env_path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


def split_csv(value):
    """把英文逗号分隔的配置拆成列表，并过滤空字符串。"""
    return [item.strip() for item in str(value).split(",") if item.strip()]


def env_str(name, default=""):
    """读取字符串环境变量。"""
    return os.getenv(name, default)


def env_int(name, default):
    """读取整数环境变量，配置格式错误时返回默认值。"""
    value = os.getenv(name)
    if value is None or value == "":
        return default

    try:
        return int(value)
    except ValueError:
        return default


def env_float(name, default):
    """读取浮点数环境变量，配置格式错误时返回默认值。"""
    value = os.getenv(name)
    if value is None or value == "":
        return default

    try:
        return float(value)
    except ValueError:
        return default


def env_bool(name, default=False):
    """读取布尔环境变量，支持 true/false、1/0、yes/no 等常见写法。"""
    value = os.getenv(name)
    if value is None or value == "":
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def resolve_output_dir(path_text):
    """把输出目录解析为绝对路径；相对路径默认位于 QCWY 项目目录下。"""
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return BASE_DIR / path


@dataclass
class SpiderConfig:
    """保存前程无忧爬虫的一次运行配置。"""

    fetch_mode: str
    keywords: list[str]
    cities: list[str]
    max_pages: int
    page_size: int
    request_delay_seconds: float
    output_dir: Path
    save_raw_json: bool
    save_csv: bool
    save_excel: bool
    timeout_seconds: int
    cookie: str
    browser_headless: bool
    browser_user_data_dir: Path
    browser_wait_seconds: int
    browser_executable_path: str
    browser_disable_no_sandbox: bool

    @classmethod
    def from_cli(cls):
        """从 .env 和命令行参数合并生成配置；命令行参数优先级更高。"""
        load_env()

        parser = argparse.ArgumentParser(description="前程无忧岗位信息采集工具")
        parser.add_argument("--keyword", help="岗位关键词，多个关键词用英文逗号分隔")
        parser.add_argument("--city", help="城市名称或城市编码，多个城市用英文逗号分隔")
        parser.add_argument("--pages", type=int, help="每个关键词 + 城市组合采集页数")
        parser.add_argument("--page-size", type=int, help="每页岗位数量")
        parser.add_argument("--output-dir", help="输出目录")
        parser.add_argument("--mode", choices=["browser", "requests"], help="采集模式：browser 或 requests")
        args = parser.parse_args()

        # 命令行没有传值时，回退到 .env；.env 没有传值时，使用保守默认值。
        keywords_text = args.keyword or env_str("QCWY_KEYWORDS", "测试工程师")
        cities_text = args.city or env_str("QCWY_CITIES", "上海")
        output_dir_text = args.output_dir or env_str("QCWY_OUTPUT_DIR", "data")

        return cls(
            fetch_mode=args.mode or env_str("QCWY_FETCH_MODE", "browser"),
            keywords=split_csv(keywords_text),
            cities=split_csv(cities_text),
            max_pages=args.pages or env_int("QCWY_MAX_PAGES", 1),
            page_size=args.page_size or env_int("QCWY_PAGE_SIZE", 20),
            request_delay_seconds=env_float("QCWY_REQUEST_DELAY_SECONDS", 2),
            output_dir=resolve_output_dir(output_dir_text),
            save_raw_json=env_bool("QCWY_SAVE_RAW_JSON", True),
            save_csv=env_bool("QCWY_SAVE_CSV", True),
            save_excel=env_bool("QCWY_SAVE_EXCEL", True),
            timeout_seconds=env_int("QCWY_TIMEOUT_SECONDS", 20),
            cookie=env_str("QCWY_COOKIE", ""),
            browser_headless=env_bool("QCWY_BROWSER_HEADLESS", False),
            browser_user_data_dir=resolve_output_dir(env_str("QCWY_BROWSER_USER_DATA_DIR", ".browser_profile")),
            browser_wait_seconds=env_int("QCWY_BROWSER_WAIT_SECONDS", 25),
            browser_executable_path=env_str("QCWY_BROWSER_EXECUTABLE_PATH", ""),
            browser_disable_no_sandbox=env_bool("QCWY_BROWSER_DISABLE_NO_SANDBOX", True),
        )
