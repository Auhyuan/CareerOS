"""知识库定义、文件关联和任务提交业务服务。"""

import re
from uuid import uuid4

from sqlmodel import Session

from app.server.file.src.models.file_models import UploadedFileRecord
from app.server.knowledge.src.config import knowledge_config
from app.server.knowledge.src.ingestion.queue_service import ingestion_queue_service
from app.server.knowledge.src.models import KnowledgeBase, KnowledgeDocument
from app.server.knowledge.src.repositories import KnowledgeBaseRepository, KnowledgeDocumentRepository
from app.server.knowledge.src.split.schemas import (
    MarkdownDocumentHeaderThenRecursiveStrategyConfig,
    SplitMethodConfig,
)
from app.server.knowledge.src.schemas.knowledge_schemas import (
    IngestionRunResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeDocumentResponse,
    KnowledgeDocumentSubmitRequest,
    KnowledgeDocumentSubmitResponse,
)
from app.server.knowledge.src.vector_store.milvus_store import vector_store_service


class KnowledgeManagementService:
    """管理知识库及文件入库入口，不承担后台任务执行。"""

    def __init__(self) -> None:
        """初始化知识库与文档 Repository。"""
        self.knowledge_repository = KnowledgeBaseRepository()
        self.document_repository = KnowledgeDocumentRepository()

    async def create_knowledge_base(
        self,
        db: Session,
        request: KnowledgeBaseCreateRequest,
    ) -> KnowledgeBaseResponse:
        """创建 PostgreSQL 知识库记录及对应 Milvus Collection。"""
        knowledge_id = f"kb_{uuid4().hex}"
        collection_name = self._build_collection_name(knowledge_id)
        split_config = self._normalize_split_config(request.split_config)
        await vector_store_service.create_collection(
            collection_name=collection_name,
            model_name=knowledge_config.embedding_model,
            dimension=knowledge_config.embedding_dimension,
        )
        record = KnowledgeBase(
            knowledge_id=knowledge_id,
            name=request.name.strip(),
            description=request.description,
            collection_name=collection_name,
            embedding_model=knowledge_config.embedding_model,
            embedding_dimension=knowledge_config.embedding_dimension,
            split_config=split_config,
            extra_metadata=request.metadata,
        )
        try:
            saved = self.knowledge_repository.add(db, record)
        except Exception:
            # PostgreSQL 写入失败时回收刚创建的 Collection，避免留下孤儿资源。
            await vector_store_service.drop_collection(collection_name)
            raise
        return self.to_knowledge_response(saved)

    def search_knowledge_bases(
        self,
        db: Session,
        request: KnowledgeBaseSearchRequest,
    ) -> list[KnowledgeBaseResponse]:
        """查询知识库列表。"""
        records = self.knowledge_repository.search(db, request.keyword, request.status)
        return [self.to_knowledge_response(record) for record in records]

    def submit_document(
        self,
        db: Session,
        request: KnowledgeDocumentSubmitRequest,
    ) -> KnowledgeDocumentSubmitResponse:
        """建立知识库文件关系，并提交 ingest 或 reindex 任务。"""
        knowledge = self.knowledge_repository.get_by_knowledge_id(db, request.knowledge_id)
        if knowledge is None or knowledge.status != "active":
            raise ValueError(f"可用知识库不存在: {request.knowledge_id}")
        uploaded_file = db.get(UploadedFileRecord, request.file_id)
        if uploaded_file is None or uploaded_file.status == "deleted":
            raise ValueError(f"上传文件不存在: {request.file_id}")
        if uploaded_file.conversion_status == "failed":
            raise ValueError(f"上传文件内容源构建失败: {uploaded_file.conversion_error or '未知原因'}")

        document = self.document_repository.get_by_knowledge_and_file(
            db,
            request.knowledge_id,
            request.file_id,
        )
        if document is None:
            document = self.document_repository.add(
                db,
                KnowledgeDocument(
                    knowledge_id=request.knowledge_id,
                    file_id=request.file_id,
                ),
            )
        elif document.status == "indexed" and not request.force_reindex:
            return KnowledgeDocumentSubmitResponse(
                document=self.to_document_response(document),
                run=None,
                reused_active_run=False,
            )

        operation = "reindex" if request.force_reindex and document.status == "indexed" else "ingest"
        run, reused = ingestion_queue_service.submit(
            db,
            document=document,
            operation=operation,
            priority=request.priority,
            max_retries=knowledge_config.ingestion_max_retries,
            payload={},
        )
        db.refresh(document)
        return KnowledgeDocumentSubmitResponse(
            document=self.to_document_response(document),
            run=IngestionRunResponse.model_validate(run, from_attributes=True),
            reused_active_run=reused,
        )

    @staticmethod
    def _normalize_split_config(raw_config: dict) -> dict:
        """校验并补全知识库切片配置，避免无效配置进入数据库。"""
        config = raw_config or {
            "type": knowledge_config.split_default_method,
            "chunk_size": knowledge_config.split_chunk_size,
            "chunk_overlap": knowledge_config.split_chunk_overlap,
        }
        if config.get("type") == "markdown_document_header_then_recursive":
            return MarkdownDocumentHeaderThenRecursiveStrategyConfig.model_validate(config).model_dump()
        return SplitMethodConfig.model_validate(config).model_dump()

    @staticmethod
    def _build_collection_name(knowledge_id: str) -> str:
        """把知识库 ID 转换为合法且稳定的 Milvus Collection 名称。"""
        normalized = re.sub(r"[^0-9A-Za-z_]", "_", knowledge_id)
        return f"knowledge_{normalized}"[:255]

    @staticmethod
    def to_knowledge_response(record: KnowledgeBase) -> KnowledgeBaseResponse:
        """把知识库数据库模型转换为接口响应。"""
        return KnowledgeBaseResponse(
            knowledge_id=record.knowledge_id,
            name=record.name,
            description=record.description,
            collection_name=record.collection_name,
            embedding_model=record.embedding_model,
            embedding_dimension=record.embedding_dimension,
            split_config=record.split_config,
            status=record.status,
            metadata=record.extra_metadata,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def to_document_response(record: KnowledgeDocument) -> KnowledgeDocumentResponse:
        """把知识库文档数据库模型转换为接口响应。"""
        return KnowledgeDocumentResponse.model_validate(record, from_attributes=True)


knowledge_management_service = KnowledgeManagementService()
