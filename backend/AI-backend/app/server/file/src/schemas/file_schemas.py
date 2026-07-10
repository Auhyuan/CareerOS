from typing import Any

from pydantic import BaseModel, Field


class UploadedFileView(BaseModel):
    """上传文件返回视图。"""

    file_id: str = Field(..., description="文件 ID")
    original_name: str = Field(..., description="原始文件名")
    stored_name: str = Field(..., description="存储文件名")
    extension: str = Field(default="", description="文件扩展名")
    mime_type: str | None = Field(default=None, description="MIME 类型")
    size_bytes: int = Field(default=0, description="文件大小，单位字节")
    status: str = Field(default="uploaded", description="文件状态")
    parse_status: str = Field(default="pending", description="解析状态")
    created_at: str | None = Field(default=None, description="创建时间")
    updated_at: str | None = Field(default=None, description="更新时间")


class FileUploadResponse(BaseModel):
    """文件上传响应。"""

    files: list[UploadedFileView] = Field(default_factory=list, description="已上传文件列表")


class FileDetailRequest(BaseModel):
    """查询文件详情请求。"""

    file_id: str = Field(..., min_length=1, description="文件 ID")


class FileParseRequest(BaseModel):
    """解析文件请求。"""

    file_id: str = Field(..., min_length=1, description="文件 ID")
    parse_mode: str = Field(default="text", description="解析模式，当前支持 text/markdown")
    force: bool = Field(default=False, description="是否强制重新解析")


class FileParseResponse(BaseModel):
    """文件解析响应。"""

    file_id: str = Field(..., description="文件 ID")
    original_name: str = Field(..., description="原始文件名")
    parse_mode: str = Field(default="text", description="解析模式")
    content: str = Field(default="", description="解析后的文本内容")
    content_length: int = Field(default=0, description="文本长度")
    parse_status: str = Field(default="success", description="解析状态")


class FileDeleteRequest(BaseModel):
    """删除文件请求。"""

    file_ids: list[str] = Field(..., min_length=1, description="待删除文件 ID 列表")


class FileDeleteResponse(BaseModel):
    """删除文件响应。"""

    deleted: int = Field(default=0, description="删除数量")
    file_ids: list[str] = Field(default_factory=list, description="已删除文件 ID")


class AgentFileContext(BaseModel):
    """注入 Agent 的文件上下文。"""

    file_id: str = Field(..., description="文件 ID")
    file_name: str = Field(..., description="文件名")
    content: str = Field(default="", description="文件文本内容")
    metadata: dict[str, Any] = Field(default_factory=dict, description="文件元数据")
