"""知识库服务统一接口。"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.knowledge.src.embedding.schemas import EmbeddingInput, EmbeddingOutput
from app.server.knowledge.src.ingestion.queue_service import ingestion_queue_service
from app.server.knowledge.src.retrieval.schemas import RetrievalInput, RetrievalOutput
from app.server.knowledge.src.schemas.knowledge_schemas import (
    IngestionRetryRequest,
    IngestionRunQueryRequest,
    IngestionRunResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeDocumentSubmitRequest,
    KnowledgeDocumentSubmitResponse,
)
from app.server.knowledge.src.services.knowledge_management_service import knowledge_management_service
from app.server.knowledge.src.services.knowledge_service import knowledge_service
from app.server.knowledge.src.split.schemas import SplitInput, SplitOutput


router = APIRouter(prefix="/knowledge")


@router.get("/health", response_model=Result[dict[str, str]], summary="知识库服务存活检查")
def knowledge_health() -> Result[dict[str, str]]:
    """只检查知识库路由是否已经挂载，不检查外部依赖。"""
    return Result.success({"service": "knowledge", "status": "ok"})


@router.get("/health/readiness", response_model=Result[dict[str, Any]], summary="知识库依赖就绪检查")
async def knowledge_readiness() -> Result[dict[str, Any]]:
    """真实检查 PostgreSQL 和 Milvus 是否已经可用。"""
    return Result.success(await knowledge_service.readiness())


@router.get("/capabilities", response_model=Result[dict[str, Any]], summary="查询知识库能力")
def get_knowledge_capabilities() -> Result[dict[str, Any]]:
    """查询当前已经接入的切片、向量化、检索和入库能力。"""
    return Result.success(knowledge_service.get_capabilities())


@router.post("/bases/create", response_model=Result[KnowledgeBaseResponse], summary="创建知识库")
async def create_knowledge_base(
    request: KnowledgeBaseCreateRequest,
    db: Session = Depends(get_postgres_engine),
) -> Result[KnowledgeBaseResponse]:
    """创建知识库记录和对应的 Milvus Collection。"""
    return Result.success(await knowledge_management_service.create_knowledge_base(db, request))


@router.post("/bases/search", response_model=Result[list[KnowledgeBaseResponse]], summary="查询知识库列表")
def search_knowledge_bases(
    request: KnowledgeBaseSearchRequest,
    db: Session = Depends(get_postgres_engine),
) -> Result[list[KnowledgeBaseResponse]]:
    """按照关键字和状态查询知识库。"""
    return Result.success(knowledge_management_service.search_knowledge_bases(db, request))


@router.post(
    "/documents/submit",
    response_model=Result[KnowledgeDocumentSubmitResponse],
    summary="提交知识库文件入库任务",
)
def submit_knowledge_document(
    request: KnowledgeDocumentSubmitRequest,
    db: Session = Depends(get_postgres_engine),
) -> Result[KnowledgeDocumentSubmitResponse]:
    """关联上传文件并提交 PostgreSQL 入库任务。"""
    return Result.success(knowledge_management_service.submit_document(db, request))


@router.post("/ingestion/status", response_model=Result[IngestionRunResponse], summary="查询入库任务状态")
def get_ingestion_status(
    request: IngestionRunQueryRequest,
    db: Session = Depends(get_postgres_engine),
) -> Result[IngestionRunResponse]:
    """根据 run_id 查询排队、执行、重试和完成状态。"""
    run = ingestion_queue_service.get(db, request.run_id)
    if run is None:
        raise ValueError(f"入库任务不存在: {request.run_id}")
    return Result.success(IngestionRunResponse.model_validate(run, from_attributes=True))


@router.post("/ingestion/retry", response_model=Result[IngestionRunResponse], summary="重新提交失败入库任务")
def retry_ingestion_run(
    request: IngestionRetryRequest,
    db: Session = Depends(get_postgres_engine),
) -> Result[IngestionRunResponse]:
    """把失败任务复制为新的待执行任务，原任务记录继续保留。"""
    run = ingestion_queue_service.retry_failed(db, request.run_id)
    return Result.success(IngestionRunResponse.model_validate(run, from_attributes=True))


@router.post("/split/preview", response_model=Result[SplitOutput], summary="预览文本切片")
def preview_split(request: SplitInput) -> Result[SplitOutput]:
    """直接切分一段文本，用于调试切片参数，不执行知识库入库。"""
    return Result.success(knowledge_service.split_text(request))


@router.post("/embedding/preview", response_model=Result[EmbeddingOutput], summary="预览文本向量")
async def preview_embedding(request: EmbeddingInput) -> Result[EmbeddingOutput]:
    """调用 Embedding 模型生成临时向量，不写入 Milvus。"""
    return Result.success(await knowledge_service.embed_text(request))


@router.post("/retrieval/search", response_model=Result[RetrievalOutput], summary="执行底层知识检索")
async def search_collections(request: RetrievalInput) -> Result[RetrievalOutput]:
    """按 Collection 执行底层检索；正式 kb_ids 映射后续补充。"""
    return Result.success(await knowledge_service.retrieve(request))
