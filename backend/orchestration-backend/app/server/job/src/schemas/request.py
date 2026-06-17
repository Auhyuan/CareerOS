from typing import Literal

from pydantic import BaseModel, Field


class JobRawRecordSearchRequest(BaseModel):
    """原始岗位列表查询请求模型。"""

    keyword: str | None = Field(default=None, description="岗位标题或 JD 正文关键字")
    city: str | None = Field(default=None, description="城市筛选")
    platform: str | None = Field(default=None, description="平台筛选，例如 qcwy")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class JobDirectionSearchRequest(BaseModel):
    """岗位方向查询请求模型。"""

    keyword: str | None = Field(default=None, description="岗位方向关键字")
    status: str | None = Field(default="active", description="岗位方向状态")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class QcwyJobCrawlAndIngestRequest(BaseModel):
    """前程无忧岗位采集并写入原始岗位池的编排请求模型。"""

    keywords: list[str] = Field(default_factory=lambda: ["测试工程师"], description="岗位关键字列表")
    cities: list[str] = Field(default_factory=lambda: ["上海"], description="城市名称或城市编码列表")
    pages: int = Field(default=1, ge=1, le=10, description="每个关键字和城市组合采集的页数")
    page_size: int = Field(default=20, ge=1, le=50, description="每页岗位数量")
    fetch_mode: Literal["browser", "requests"] = Field(default="browser", description="采集模式")
    fields: list[str] | None = Field(default=None, description="需要返回的字段列表；为空则返回全部字段")
    save_raw_json: bool = Field(default=True, description="是否让能力层保存原始 JSON 文件")
    save_csv: bool = Field(default=True, description="是否让能力层保存 CSV 文件")
    save_excel: bool = Field(default=True, description="是否让能力层保存 Excel 文件")
    persist_to_db: bool = Field(default=True, description="是否把采集结果写入原始岗位池")
    browser_headless: bool = Field(default=False, description="浏览器是否无头运行")
    browser_executable_path: str = Field(default="", description="本机 Chrome/Edge 浏览器路径")
    browser_wait_seconds: int = Field(default=25, ge=5, le=120, description="等待岗位接口响应的秒数")
