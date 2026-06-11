from pydantic import BaseModel, Field


class JobPostingSearchRequest(BaseModel):
    """岗位列表查询请求模型。"""

    keyword: str | None = Field(default=None, description="岗位标题关键词")
    city: str | None = Field(default=None, description="城市筛选")
    platform: str | None = Field(default=None, description="平台筛选，例如 qcwy")
    status: str | None = Field(default=None, description="岗位状态筛选，例如 recruiting")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
