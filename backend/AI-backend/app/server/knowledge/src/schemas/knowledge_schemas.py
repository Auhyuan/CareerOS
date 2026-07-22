"""知识库管理和入库任务接口模型。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.server.knowledge.src.split.schemas import SplitMethodConfig, SplitStrategyConfig


class KnowledgeBaseCreateRequest(BaseModel):
    """创建知识库请求。"""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    embedding_model_code: str = Field(min_length=1, max_length=100)
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
    embedding_model_code: str
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
    split_method: SplitMethodConfig | None = Field(
        default=None,
        description="本次文档使用的单一切片方式；为空时继承知识库默认配置",
    )
    split_strategy: SplitStrategyConfig | None = Field(
        default=None,
        description="本次文档使用的组合切片策略；为空时继承知识库默认配置",
    )

    @model_validator(mode="after")
    def validate_split_selection(self) -> "KnowledgeDocumentSubmitRequest":
        """限制单一切片方式和组合切片策略只能选择其中一种。"""
        if self.split_method is not None and self.split_strategy is not None:
            raise ValueError("split_method 和 split_strategy 只能选择一个")
        return self


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
