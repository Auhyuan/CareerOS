from pydantic import BaseModel, Field


class SpiderCrawlResponse(BaseModel):
    """爬虫采集响应数据。"""

    platform: str = Field(description="招聘平台名称")
    total: int = Field(description="采集到的岗位数量")
    rows: list[dict] = Field(default_factory=list, description="岗位数据")
    csv_path: str | None = Field(default=None, description="CSV 输出路径")
    excel_path: str | None = Field(default=None, description="Excel 输出路径")
