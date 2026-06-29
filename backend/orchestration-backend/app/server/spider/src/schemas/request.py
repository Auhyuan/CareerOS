from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QcwyBrowserSettings(BaseSettings):
    """前程无忧浏览器运行配置。"""

    # 从 backend/.env 读取本机浏览器路径等运行配置，避免把本地路径写死在代码里。
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qcwy_browser_executable_path: str = ""


class QcwyJobCrawlRequest(BaseModel):
    """前程无忧岗位采集请求参数。"""

    keywords: list[str] = Field(default_factory=lambda: ["测试工程师"], description="岗位关键词列表")
    cities: list[str] = Field(default_factory=lambda: ["上海"], description="城市名称或城市编码列表")
    pages: int = Field(default=1, ge=1, le=10, description="每个关键词和城市组合采集的页数")
    page_size: int = Field(default=20, ge=1, le=50, description="每页岗位数量")
    fetch_mode: Literal["browser", "requests"] = Field(default="browser", description="采集模式")
    fields: list[str] | None = Field(default=None, description="需要返回的字段列表；为空则返回全部字段")
    save_raw_json: bool = Field(default=False, description="是否保存原始 JSON 文件")
    save_csv: bool = Field(default=False, description="是否保存 CSV 文件")
    save_excel: bool = Field(default=False, description="是否保存 Excel 文件")
    browser_headless: bool = Field(default=False, description="浏览器是否无头运行")
    browser_executable_path: str = Field(
        default_factory=lambda: QcwyBrowserSettings().qcwy_browser_executable_path,
        description="本机 Chrome/Edge 浏览器路径",
    )
    browser_wait_seconds: int = Field(default=25, ge=5, le=120, description="等待岗位接口响应的秒数")
