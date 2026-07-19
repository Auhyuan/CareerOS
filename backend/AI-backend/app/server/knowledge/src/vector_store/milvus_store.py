import asyncio
import hashlib
import os

from app.server.knowledge.src.config import knowledge_config as settings
from app.server.knowledge.src.embedding.schemas import PersistentOptions
from app.server.knowledge.src.logging_config import logger


class MilvusVectorStoreService:
    """负责将单条 chunk 向量写入当前知识库使用的 Milvus collection。"""

    def __init__(self) -> None:
        """初始化 Milvus 服务状态，连接在首次写入时按需建立。"""
        alias_seed = hashlib.sha256(settings.milvus_uri.encode("utf-8")).hexdigest()[:8]
        self.connection_alias = f"primitive_embedding_{alias_seed}"
        self._connection_lock = asyncio.Lock()
        # collection 创建属于低频基础设施操作，使用全局锁避免并发请求重复创建同名集合。
        self._collection_lock = asyncio.Lock()

    async def close(self) -> None:
        """关闭当前原子服务创建的 Milvus 连接。"""
        await asyncio.to_thread(self._disconnect)

    async def health_check(self) -> str:
        """
        检查 Milvus 连接以及目标 database 是否可用。

        Returns:
            str: 已成功切换并验证的 Milvus database 名称
        """
        await self._ensure_connection()
        return settings.milvus_database

    async def create_collection(self, *, collection_name: str, model_name: str, dimension: int) -> None:
        """显式创建 Milvus collection，供 create_collection operation 调用。"""
        await self._ensure_connection()
        await self._ensure_collection(
            collection_name=collection_name,
            model_name=model_name,
            dimension=dimension,
        )

    async def ensure_collection_exists(self, collection_name: str) -> None:
        """校验 Milvus collection 已存在；不存在时不再隐式创建。"""
        await self._ensure_connection()
        exists = await asyncio.to_thread(self._has_collection_sync, collection_name)
        if not exists:
            raise ValueError(f"Milvus collection not found: {collection_name}")

    async def drop_collection(self, collection_name: str) -> bool:
        """删除 Milvus collection；不存在时返回 False，保证删除操作幂等。"""
        await self._ensure_connection()
        return await asyncio.to_thread(self._drop_collection_sync, collection_name)

    async def delete_file_vectors(self, collection_name: str, file_id: str) -> None:
        """删除 Collection 中属于指定文件的全部向量，供重试和重建前清理旧索引。"""
        await self._ensure_connection()
        await self.ensure_collection_exists(collection_name)
        await asyncio.wait_for(
            asyncio.to_thread(self._delete_file_vectors_sync, collection_name, file_id),
            timeout=settings.milvus_write_timeout,
        )


    async def insert(
        self,
        text: str,
        embedding: list[float],
        options: PersistentOptions,
        model_name: str,
        expected_dimension: int,
    ) -> str:
        """
        将单条 chunk 及其向量插入 Milvus。

        Args:
            text: chunk 正文
            embedding: embedding 模型生成的向量
            options: 知识库和 chunk 上下文
            model_name: 本次使用的Embedding模型名称
            expected_dimension: 本次模型预期向量维度

        Returns:
            str: 写入使用的向量主键，即 chunk_id
        """
        self._validate_record(
            text=text,
            embedding=embedding,
            options=options,
            expected_dimension=expected_dimension,
        )
        await self._ensure_connection()
        await self.ensure_collection_exists(options.collection_name)

        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._insert_sync,
                    text,
                    embedding,
                    options,
                ),
                timeout=settings.milvus_write_timeout,
            )
        except TimeoutError as exc:
            raise TimeoutError(
                f"Milvus insert timeout after {settings.milvus_write_timeout}s"
            ) from exc

        return options.chunk_id

    async def _ensure_connection(self) -> None:
        """确保 Milvus 连接已建立，并切换到配置的数据库。"""
        async with self._connection_lock:
            await asyncio.wait_for(
                asyncio.to_thread(self._connect_sync),
                timeout=settings.milvus_connect_timeout,
            )

    async def _ensure_collection(
        self,
        collection_name: str,
        model_name: str,
        dimension: int,
    ) -> None:
        """
        确保目标 collection 存在。

        collection 不存在时，按照当前知识库项目的固定 schema 和索引配置自动创建。
        """
        async with self._collection_lock:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._create_collection_if_missing_sync,
                    collection_name,
                    model_name,
                    dimension,
                ),
                timeout=settings.milvus_write_timeout,
            )

    def _has_collection_sync(self, collection_name: str) -> bool:
        """同步检查 Milvus collection 是否存在。"""
        from pymilvus import utility

        return bool(utility.has_collection(collection_name, using=self.connection_alias))

    def _drop_collection_sync(self, collection_name: str) -> bool:
        """同步删除 Milvus collection。"""
        from pymilvus import utility

        if not utility.has_collection(collection_name, using=self.connection_alias):
            return False
        utility.drop_collection(collection_name, using=self.connection_alias)
        logger.info("Milvus collection 已删除：collection=%s", collection_name)
        return True

    def _connect_sync(self) -> None:
        """同步建立 Milvus 连接，供 asyncio.to_thread 调用。"""
        from pymilvus import connections, db

        if not connections.has_connection(self.connection_alias):
            connections.connect(
                alias=self.connection_alias,
                uri=settings.milvus_uri,
                token=settings.milvus_token or None,
                timeout=settings.milvus_connect_timeout,
            )

        databases = db.list_database(using=self.connection_alias)
        if settings.milvus_database not in databases:
            raise ValueError(f"Milvus database not found: {settings.milvus_database}")
        db.using_database(settings.milvus_database, using=self.connection_alias)

    def _insert_sync(
        self,
        text: str,
        embedding: list[float],
        options: PersistentOptions,
    ) -> None:
        """按照当前知识库 Milvus schema 执行单条 insert。"""
        from pymilvus import Collection

        collection_name = options.collection_name
        collection = Collection(name=collection_name, using=self.connection_alias)
        self._validate_collection_schema(collection, embedding)

        # 字段顺序严格对齐当前知识库项目：
        # id, content, source, chunk_id, file_id, chunk_index, embedding。
        # Build entities according to the target collection schema. New collections include
        # metadata JSON, while legacy collections still use the original seven-column schema.
        has_metadata = self._collection_has_field(collection, "metadata")
        entities = self._build_insert_entities(
            text=text,
            embedding=embedding,
            options=options,
            has_metadata=has_metadata,
        )
        collection.insert(entities, timeout=settings.milvus_write_timeout)

    def _delete_file_vectors_sync(self, collection_name: str, file_id: str) -> None:
        """同步删除指定文件向量；转义引号以避免构造非法 Milvus 表达式。"""
        from pymilvus import Collection

        safe_file_id = file_id.replace("\\", "\\\\").replace('"', '\\"')
        collection = Collection(name=collection_name, using=self.connection_alias)
        collection.delete(
            expr=f'file_id == "{safe_file_id}"',
            timeout=settings.milvus_write_timeout,
        )

    @staticmethod
    def _collection_has_field(collection, field_name: str) -> bool:
        """判断目标 Collection 的 Schema 是否包含指定字段。"""
        return any(
            getattr(field, "name", None) == field_name
            for field in getattr(collection.schema, "fields", [])
        )

    @staticmethod
    def _build_insert_entities(
        *,
        text: str,
        embedding: list[float],
        options: PersistentOptions,
        has_metadata: bool,
    ) -> list[list]:
        """为旧版和支持 metadata 的 Schema 构造 Milvus 写入实体。"""
        if not has_metadata and options.metadata:
            raise ValueError("target Milvus collection does not support metadata")

        entities = [
            [options.chunk_id],
            [text],
            [options.source],
            [options.chunk_id],
            [options.file_id],
            [options.chunk_index],
        ]
        if has_metadata:
            # Inject source (usually the file name) into metadata so retrieval-side
            # metadata_headers can distinguish same-title chunks from different documents.
            # The file extension is stripped because users rarely include it in queries.
            enriched = dict(options.metadata or {})
            if options.source and "file_name" not in enriched:
                enriched["file_name"] = os.path.splitext(options.source)[0]
            entities.append([enriched])
        entities.append([embedding])
        return entities

    def _create_collection_if_missing_sync(
        self,
        collection_name: str,
        model_name: str,
        dimension: int,
    ) -> None:
        """同步检查并创建 Milvus collection。"""
        from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, utility

        if utility.has_collection(collection_name, using=self.connection_alias):
            return

        # 字段定义严格对齐当前知识库项目的普通 Milvus collection schema。
        try:
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(
                    name="content",
                    dtype=DataType.VARCHAR,
                    max_length=65535,
                    enable_analyzer=True,
                    enable_match=True,
                ),
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=dimension,
                ),
            ]
        except Exception:
            # 兼容不支持全文检索字段参数的旧版 pymilvus/Milvus。
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=dimension,
                ),
            ]

        schema = CollectionSchema(
            fields=fields,
            description=f"Embedding collection {collection_name} using {model_name}",
        )

        try:
            collection = Collection(
                name=collection_name,
                schema=schema,
                using=self.connection_alias,
            )
        except Exception:
            # 多进程部署时本地锁无法覆盖其他进程；若其他进程已创建成功，则直接复用。
            if utility.has_collection(collection_name, using=self.connection_alias):
                return
            raise

        # 创建与主知识库项目一致的 COSINE 向量索引。
        collection.create_index(
            "embedding",
            {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024},
            },
        )

        # content 全文索引和 file_id 过滤索引属于增强能力，失败时不阻断向量写入。
        try:
            collection.create_index(
                "content",
                {
                    "index_type": "INVERTED",
                    "index_name": "content_inverted_index",
                },
            )
        except Exception as exc:
            logger.warning("Milvus content index creation skipped: %s", exc)

        try:
            collection.create_index(
                "file_id",
                {
                    "index_type": "INVERTED",
                    "index_name": "file_id_index",
                },
            )
        except Exception as exc:
            logger.warning("Milvus file_id index creation skipped: %s", exc)

        logger.info(
            "Milvus collection created: collection=%s dimension=%s",
            collection_name,
            dimension,
        )

    def _validate_record(
        self,
        text: str,
        embedding: list[float],
        options: PersistentOptions,
        expected_dimension: int,
    ) -> None:
        """在请求 Milvus 前校验字段长度和向量维度。"""
        if len(options.chunk_id) > 100:
            raise ValueError("chunk_id length cannot exceed 100")
        if len(options.file_id) > 100:
            raise ValueError("file_id length cannot exceed 100")
        if len(options.source) > 500:
            raise ValueError("source length cannot exceed 500")
        if len(text) > 65535:
            raise ValueError("text length cannot exceed Milvus content limit 65535")
        if len(embedding) != expected_dimension:
            raise ValueError(
                f"embedding dimension mismatch: expected {expected_dimension}, got {len(embedding)}"
            )

    def _validate_collection_schema(self, collection, embedding: list[float]) -> None:
        """校验目标 collection 字段和向量维度是否与当前知识库 schema 一致。"""
        required_fields = {
            "id",
            "content",
            "source",
            "chunk_id",
            "file_id",
            "chunk_index",
            "embedding",
        }
        schema_fields = {
            field.name: field
            for field in getattr(collection.schema, "fields", [])
        }
        missing_fields = required_fields - set(schema_fields)
        if missing_fields:
            raise ValueError(
                f"Milvus collection schema mismatch, missing fields: {sorted(missing_fields)}"
            )

        embedding_field = schema_fields["embedding"]
        field_params = getattr(embedding_field, "params", None) or {}
        collection_dimension = int(field_params.get("dim") or 0)
        if collection_dimension and collection_dimension != len(embedding):
            raise ValueError(
                "Milvus collection embedding dimension mismatch: "
                f"collection={collection_dimension}, vector={len(embedding)}"
            )

    def _disconnect(self) -> None:
        """同步断开 Milvus 连接。"""
        try:
            from pymilvus import connections

            if connections.has_connection(self.connection_alias):
                connections.disconnect(self.connection_alias)
        except ImportError:
            # 未安装 pymilvus 时无需执行连接清理。
            return


# 模块级单例，供路由和应用生命周期复用。
vector_store_service = MilvusVectorStoreService()
