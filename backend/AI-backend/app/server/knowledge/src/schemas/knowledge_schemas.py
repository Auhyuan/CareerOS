"""知识库管理和入库任务接口模型。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class KnowledgeBaseCreateRequest(BaseModel):
    """创建知识库请求。"""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    split_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseSearchRequest(BaseModel):
    """查询知识库列表请求。"""

    keyword: str | None = None
    status: Literal["active", "disabled", "deleted"] | None = None


class KnowledgeBaseResponse(BaseModel):
    """知识库详情响应。"""

    knowledge_id: str
    name: str
    description: str | None
    collection_name: str
    embedding_model: str
    embedding_dimension: int
    split_config: dict[str, Any]
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentSubmitRequest(BaseModel):
    """向知识库添加文件并提交入库任务。"""

    knowledge_id: str = Field(min_length=1, max_length=100)
    file_id: str = Field(min_length=1, max_length=100)
    force_reindex: bool = False
    priority: int = Field(default=0, ge=-100, le=100)


class IngestionRunQueryRequest(BaseModel):
    """查询单个入库任务请求。"""

    run_id: str = Field(min_length=1, max_length=100)


class IngestionRetryRequest(BaseModel):
    """人工重新提交失败入库任务请求。"""

    run_id: str = Field(min_length=1, max_length=100)


class IngestionRunResponse(BaseModel):
    """入库任务状态响应。"""

    run_id: str
    document_id: int
    knowledge_id: str
    file_id: str
    operation: str
    status: str
    priority: int
    worker_id: str | None
    retry_count: int
    max_retries: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class KnowledgeDocumentResponse(BaseModel):
    """知识库文件关系及索引状态响应。"""

    id: int
    knowledge_id: str
    file_id: str
    status: str
    index_version: int
    chunk_count: int
    error_message: str | None
    indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentSubmitResponse(BaseModel):
    """提交知识库文件后的文档关系和任务响应。"""

    document: KnowledgeDocumentResponse
    run: IngestionRunResponse | None
    reused_active_run: bool = False
