from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[5]
SPIDER_RUNTIME_DIR = BACKEND_DIR / ".runtime" / "spider"
QCWY_RUNTIME_DIR = SPIDER_RUNTIME_DIR / "qcwy"

# 前程无忧爬虫默认输出目录。
# 说明：运行产物不要放在 src 源码目录下，避免后续源码结构被 data、debug、浏览器 profile 污染。
QCWY_DEFAULT_OUTPUT_DIR = QCWY_RUNTIME_DIR / "data"

# 前程无忧浏览器模式默认用户数据目录。
# 说明：Playwright 会把 Cookie、缓存、登录态写入这个目录，用于降低每次运行都重新验证的概率。
QCWY_DEFAULT_PROFILE_DIR = QCWY_RUNTIME_DIR / ".browser_profile"
