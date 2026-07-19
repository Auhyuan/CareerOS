"""知识库统一服务门面。"""

import asyncio
from typing import Any

from app.server.knowledge.src.config import knowledge_config
from app.server.knowledge.src.embedding.schemas import EmbeddingInput, EmbeddingOutput
from app.server.knowledge.src.embedding.service import embedding_service
from app.server.knowledge.src.ingestion.worker import ingestion_worker_manager
from app.server.knowledge.src.logging_config import logger
from app.server.knowledge.src.retrieval.milvus_store import milvus_store
from app.server.knowledge.src.retrieval.rerank_client import rerank_client
from app.server.knowledge.src.retrieval.retrieval_service import retrieval_service
from app.server.knowledge.src.retrieval.schemas import RetrievalInput, RetrievalOutput
from app.server.knowledge.src.split.schemas import SplitInput, SplitMethodConfig, SplitOutput
from app.server.knowledge.src.split.service import split_service
from app.server.knowledge.src.vector_store.milvus_store import vector_store_service


class KnowledgeService:
    """对外提供统一的知识库能力入口，并隐藏底层组件组织方式。"""

    def get_capabilities(self) -> dict[str, Any]:
        """返回当前知识库模块已经实现和暂未启用的能力。"""
        return {
            "split": {
                "enabled": True,
                "methods": ["markdown", "markdown_header", "recursive_character", "character", "qa_separator"],
                "strategies": ["markdown_document_header_then_recursive"],
            },
            "embedding": {"enabled": True, "model": knowledge_config.embedding_model},
            "retrieval": {
                "enabled": True,
                "modes": ["vector", "keyword", "hybrid", "document"],
                "rerank_configured": bool(knowledge_config.rerank_base_url),
            },
            "ingestion": {
                "enabled": True,
                "worker_enabled": knowledge_config.ingestion_worker_enabled,
                "queue": "postgresql_skip_locked",
            },
        }

    def split_text(self, request: SplitInput) -> SplitOutput:
        """使用指定方式或默认方式切分调用方直接提供的文本。"""
        if not request.text:
            raise ValueError("切片预览必须直接提供 text；file_id 将由后续入库流程统一处理")
        method = request.split_method or SplitMethodConfig(
            type=knowledge_config.split_default_method,
            chunk_size=knowledge_config.split_chunk_size,
            chunk_overlap=knowledge_config.split_chunk_overlap,
        )
        result = split_service.split(text=request.text, method=method, strategy=request.split_strategy)
        return SplitOutput(
            chunk_count=len(result["chunks"]),
            chunks=result["chunks"],
            split_method=result["split_method"],
            split_strategy=result["split_strategy"],
            effective_config=result["effective_config"],
        )

    async def embed_text(self, request: EmbeddingInput) -> EmbeddingOutput:
        """生成临时向量，不执行 Collection 创建或向量持久化。"""
        model_config = request.embedding_model_config
        model_name = model_config.model_name if model_config else knowledge_config.embedding_model
        expected_dimension = model_config.dimension if model_config else knowledge_config.embedding_dimension
        vector = await embedding_service.embed_text(
            request.text,
            model=model_name,
            extra_params=request.extra_params,
        )
        if len(vector) != expected_dimension:
            raise ValueError(f"Embedding 向量维度不匹配: expected={expected_dimension}, actual={len(vector)}")
        return EmbeddingOutput(model_name=model_name, dimension=len(vector), embedding=vector)

    async def retrieve(self, request: RetrievalInput) -> RetrievalOutput:
        """执行底层 Collection 检索；正式知识库 API 后续负责 kb_id 映射。"""
        return await retrieval_service.retrieve(request)

    async def startup(self) -> None:
        """执行本地能力检查，并按配置选择是否检查外部依赖。"""
        split_service.health_check()
        logger.info("知识库本地切片能力检查通过")
        if not knowledge_config.knowledge_startup_dependency_check:
            logger.info("知识库外部依赖检查已跳过，可通过 KNOWLEDGE_STARTUP_DEPENDENCY_CHECK 开启")
        else:
            checks: list[tuple[str, Any]] = [
                ("embedding", embedding_service.health_check()),
                ("milvus", milvus_store.health_check()),
            ]
            if knowledge_config.rerank_base_url:
                checks.append(("rerank", rerank_client.health_check()))

            results = await asyncio.gather(
                *(asyncio.wait_for(check, timeout=knowledge_config.startup_health_check_timeout) for _, check in checks),
                return_exceptions=True,
            )
            for (name, _), result in zip(checks, results, strict=True):
                if isinstance(result, Exception):
                    logger.warning("知识库外部依赖检查失败: component=%s reason=%s", name, result)
                else:
                    logger.info("知识库外部依赖检查通过: component=%s result=%s", name, result)
        await ingestion_worker_manager.start()

    async def close(self) -> None:
        """关闭知识库模块持有的 HTTP 与 Milvus 连接。"""
        await ingestion_worker_manager.stop()
        await asyncio.gather(
            embedding_service.close(),
            rerank_client.close(),
            milvus_store.close(),
            vector_store_service.close(),
            return_exceptions=True,
        )


knowledge_service = KnowledgeService()

