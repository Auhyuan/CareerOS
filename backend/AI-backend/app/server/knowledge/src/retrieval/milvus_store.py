"""Retrieval 使用的 Milvus 只读存储适配器。"""

import asyncio
import hashlib
import json
import re
from collections import Counter
from typing import Any

from app.server.knowledge.src.config import knowledge_config as settings
from app.server.knowledge.src.retrieval.schemas import RetrievalChunk
from app.server.knowledge.src.retrieval.exceptions import (
    RetrievalDependencyError,
    RetrievalNotFoundError,
    RetrievalValidationError,
)


class MilvusRetrievalStore:
    """负责连接 Milvus并执行只读向量检索与关键词检索。"""

    BASE_REQUIRED_FIELDS = {
        "content",
        "source",
        "chunk_id",
        "file_id",
        "chunk_index",
    }
    VECTOR_REQUIRED_FIELDS = BASE_REQUIRED_FIELDS | {
        "embedding",
    }
    METADATA_HEADERS_MIN_SCORE = 0.3

    def __init__(self) -> None:
        """初始化连接别名和并发连接锁。"""
        alias_seed = hashlib.sha256(settings.milvus_uri.encode("utf-8")).hexdigest()[:8]
        self.connection_alias = f"primitive_retrieval_{alias_seed}"
        self._connection_lock = asyncio.Lock()

    async def close(self) -> None:
        """关闭当前原子服务建立的 Milvus 连接。"""
        await asyncio.to_thread(self._disconnect_sync)

    async def health_check(self) -> str:
        """建立真实连接并确认目标 Milvus database 可用。"""
        await self._ensure_connection()
        return settings.milvus_database

    async def vector_search(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        fetch_k: int,
        top_k: int,
        similarity_threshold: float,
        file_ids: list[str],
    ) -> list[RetrievalChunk]:
        """执行 COSINE 向量检索，并将 Milvus Hit 转换为稳定 Chunk 模型。"""
        await self._ensure_connection()
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._vector_search_sync,
                    collection_name,
                    query_vector,
                    fetch_k,
                    top_k,
                    similarity_threshold,
                    file_ids,
                ),
                timeout=settings.milvus_query_timeout,
            )
        except (RetrievalNotFoundError, RetrievalValidationError):
            raise
        except TimeoutError as exc:
            raise RetrievalDependencyError(
                f"Milvus query timeout after {settings.milvus_query_timeout}s"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise RetrievalDependencyError(f"Milvus vector search failed: {exc}") from exc

    async def keyword_search(
        self,
        *,
        collection_name: str,
        query: str,
        fetch_k: int,
        top_k: int,
        file_ids: list[str],
    ) -> list[RetrievalChunk]:
        """
        使用 Milvus TEXT_MATCH 对 content 字段执行关键词检索。

        TEXT_MATCH 只返回布尔匹配结果，不提供 BM25 分数；本方法使用返回顺序
        生成 1 / (rank + 1) 排名分数，供响应和后续 RRF 融合使用。
        """
        await self._ensure_connection()
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._keyword_search_sync,
                    collection_name,
                    query,
                    fetch_k,
                    top_k,
                    file_ids,
                ),
                timeout=settings.milvus_query_timeout,
            )
        except (RetrievalNotFoundError, RetrievalValidationError):
            raise
        except TimeoutError as exc:
            raise RetrievalDependencyError(
                f"Milvus query timeout after {settings.milvus_query_timeout}s"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise RetrievalDependencyError(
                f"Milvus keyword search failed: {exc}"
            ) from exc

    async def metadata_headers_search(
        self,
        *,
        collection_name: str,
        query: str,
        fetch_k: int,
        scan_limit: int,
        file_ids: list[str],
    ) -> list[RetrievalChunk]:
        """检索标题元数据与查询匹配的切片，对外结果不暴露内部 metadata。"""
        await self._ensure_connection()
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._metadata_headers_search_sync,
                    collection_name,
                    query,
                    fetch_k,
                    scan_limit,
                    file_ids,
                ),
                timeout=settings.milvus_query_timeout,
            )
        except (RetrievalNotFoundError, RetrievalValidationError):
            raise
        except TimeoutError as exc:
            raise RetrievalDependencyError(
                f"Milvus query timeout after {settings.milvus_query_timeout}s"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise RetrievalDependencyError(
                f"Milvus metadata headers search failed: {exc}"
            ) from exc

    async def query_chunks_by_file(
        self,
        *,
        collection_name: str,
        file_id: str,
        max_chunks: int,
    ) -> list[RetrievalChunk]:
        """按 file_id 回查某个文档的全部 Chunk，并统一转换为稳定 Chunk 模型。"""
        await self._ensure_connection()
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._query_chunks_by_file_sync,
                    collection_name,
                    file_id,
                    max_chunks,
                ),
                timeout=settings.milvus_query_timeout,
            )
        except (RetrievalNotFoundError, RetrievalValidationError):
            raise
        except TimeoutError as exc:
            raise RetrievalDependencyError(
                f"Milvus query timeout after {settings.milvus_query_timeout}s"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise RetrievalDependencyError(
                f"Milvus document chunks query failed: {exc}"
            ) from exc

    async def _ensure_connection(self) -> None:
        """在并发锁内确保 Milvus 连接和 database 已准备完成。"""
        async with self._connection_lock:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._connect_sync),
                    timeout=settings.milvus_connect_timeout,
                )
            except TimeoutError as exc:
                raise RetrievalDependencyError(
                    f"Milvus connect timeout after {settings.milvus_connect_timeout}s"
                ) from exc
            except RetrievalValidationError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise RetrievalDependencyError(f"Milvus connection failed: {exc}") from exc

    def _connect_sync(self) -> None:
        """同步建立连接并切换 database，供工作线程执行。"""
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
            raise RetrievalValidationError(
                f"Milvus database not found: {settings.milvus_database}"
            )
        db.using_database(settings.milvus_database, using=self.connection_alias)

    def _vector_search_sync(
        self,
        collection_name: str,
        query_vector: list[float],
        fetch_k: int,
        top_k: int,
        similarity_threshold: float,
        file_ids: list[str],
    ) -> list[RetrievalChunk]:
        """同步执行 Collection 校验、加载和向量搜索。"""
        from pymilvus import Collection, utility

        if not utility.has_collection(collection_name, using=self.connection_alias):
            raise RetrievalNotFoundError(
                f"Milvus collection not found: {collection_name}"
            )

        collection = Collection(name=collection_name, using=self.connection_alias)
        self._validate_collection_schema(collection, len(query_vector))
        # Retrieval 只加载已有 Collection，不创建 Collection、字段或索引。
        collection.load(timeout=settings.milvus_query_timeout)

        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param={
                "metric_type": "COSINE",
                "params": {"nprobe": settings.milvus_nprobe},
            },
            limit=fetch_k,
            expr=self._build_file_filter(file_ids),
            output_fields=self._build_output_fields(collection),
            timeout=settings.milvus_query_timeout,
        )
        hits = results[0] if results else []

        chunks: list[RetrievalChunk] = []
        for hit in hits:
            # Milvus COSINE 的 distance 即相似度，值越大越相关，无需执行 1-distance。
            score = float(hit.distance)
            if score < similarity_threshold:
                continue
            chunks.append(self._build_chunk(hit=hit, score=score, collection_name=collection_name))
            if len(chunks) >= top_k:
                break
        return chunks

    def _keyword_search_sync(
        self,
        collection_name: str,
        query: str,
        fetch_k: int,
        top_k: int,
        file_ids: list[str],
    ) -> list[RetrievalChunk]:
        """同步校验 Collection 并执行 TEXT_MATCH 查询。"""
        from pymilvus import Collection, utility

        if not utility.has_collection(collection_name, using=self.connection_alias):
            raise RetrievalNotFoundError(
                f"Milvus collection not found: {collection_name}"
            )

        collection = Collection(name=collection_name, using=self.connection_alias)
        self._validate_keyword_collection_schema(collection)
        collection.load(timeout=settings.milvus_query_timeout)

        match_expression = self._build_keyword_expression(
            query=query,
            file_ids=file_ids,
        )
        results = collection.query(
            expr=match_expression,
            output_fields=self._build_output_fields(collection),
            limit=fetch_k,
            timeout=settings.milvus_query_timeout,
        )
        chunks: list[RetrievalChunk] = []
        for rank, result in enumerate(results or []):
            # TEXT_MATCH 没有相关性数值，因此这里明确返回排名分数，而非伪造相似度。
            rank_score = 1.0 / (rank + 1)
            chunks.append(
                self._build_chunk_from_values(
                    values=result,
                    score=rank_score,
                    collection_name=collection_name,
                )
            )
            if len(chunks) >= top_k:
                break
        return chunks

    def _metadata_headers_search_sync(
        self,
        collection_name: str,
        query: str,
        fetch_k: int,
        scan_limit: int,
        file_ids: list[str],
    ) -> list[RetrievalChunk]:
        """扫描 Milvus 中的 metadata.headers，并将命中记录转换为检索切片。"""
        from pymilvus import Collection, utility

        if not utility.has_collection(collection_name, using=self.connection_alias):
            raise RetrievalNotFoundError(
                f"Milvus collection not found: {collection_name}"
            )

        collection = Collection(name=collection_name, using=self.connection_alias)
        schema_fields = {
            field.name: field
            for field in getattr(collection.schema, "fields", [])
        }
        missing_fields = self.BASE_REQUIRED_FIELDS - set(schema_fields)
        if missing_fields:
            raise RetrievalValidationError(
                "Milvus collection schema mismatch, missing fields: "
                f"{sorted(missing_fields)}"
            )

        if "metadata" not in schema_fields:
            # Old collections do not have metadata yet; enhancement must not break normal retrieval.
            return []

        collection.load(timeout=settings.milvus_query_timeout)
        query_expression = self._build_file_filter(file_ids) or "chunk_index >= 0"
        results = collection.query(
            expr=query_expression,
            output_fields=[
                "content",
                "source",
                "chunk_id",
                "file_id",
                "chunk_index",
                "metadata",
            ],
            limit=scan_limit,
            timeout=settings.milvus_query_timeout,
        )
        chunks: list[RetrievalChunk] = []
        for result in results or []:
            # Only metadata.headers participates in this route; content is not used for matching here.
            score = self._score_metadata_headers(
                query=query,
                metadata=result.get("metadata"),
            )
            if score < self.METADATA_HEADERS_MIN_SCORE:
                continue
            chunks.append(
                self._build_chunk_from_values(
                    values=result,
                    score=score,
                    collection_name=collection_name,
                )
            )

        return sorted(chunks, key=lambda chunk: chunk.score, reverse=True)[:fetch_k]

    def _query_chunks_by_file_sync(
        self,
        collection_name: str,
        file_id: str,
        max_chunks: int,
    ) -> list[RetrievalChunk]:
        """同步按 file_id 查询文档 Chunk，按 chunk_index 升序返回。"""
        from pymilvus import Collection, utility

        if not utility.has_collection(collection_name, using=self.connection_alias):
            raise RetrievalNotFoundError(
                f"Milvus collection not found: {collection_name}"
            )

        collection = Collection(name=collection_name, using=self.connection_alias)
        self._validate_base_collection_schema(collection)
        collection.load(timeout=settings.milvus_query_timeout)

        # 使用 JSON 编码 file_id，避免引号或反斜线破坏 Milvus 表达式。
        file_expression = f"file_id == {json.dumps(file_id, ensure_ascii=False)}"
        results = collection.query(
            expr=file_expression,
            output_fields=self._build_output_fields(collection),
            limit=max_chunks,
            timeout=settings.milvus_query_timeout,
        )
        chunks = [
            self._build_chunk_from_values(
                values=result,
                score=0.0,
                collection_name=collection_name,
            )
            for result in (results or [])
        ]
        return sorted(chunks, key=lambda chunk: chunk.chunk_index)

    def _validate_collection_schema(self, collection: Any, vector_dimension: int) -> None:
        """校验向量检索所需字段以及 Collection 向量维度。"""
        schema_fields = {
            field.name: field
            for field in getattr(collection.schema, "fields", [])
        }
        missing_fields = self.VECTOR_REQUIRED_FIELDS - set(schema_fields)
        if missing_fields:
            raise RetrievalValidationError(
                "Milvus collection schema mismatch, missing fields: "
                f"{sorted(missing_fields)}"
            )

        embedding_field = schema_fields["embedding"]
        field_params = getattr(embedding_field, "params", None) or {}
        collection_dimension = int(field_params.get("dim") or 0)
        if not collection_dimension:
            raise RetrievalValidationError(
                "Milvus collection embedding dimension is unavailable"
            )
        if collection_dimension != vector_dimension:
            raise RetrievalValidationError(
                "Milvus collection embedding dimension mismatch: "
                f"collection={collection_dimension}, vector={vector_dimension}"
            )

    def _validate_base_collection_schema(self, collection: Any) -> None:
        """校验按 file_id 回查文档 Chunk 所需的基础字段。"""
        schema_fields = {
            field.name: field
            for field in getattr(collection.schema, "fields", [])
        }
        missing_fields = self.BASE_REQUIRED_FIELDS - set(schema_fields)
        if missing_fields:
            raise RetrievalValidationError(
                "Milvus collection schema mismatch, missing fields: "
                f"{sorted(missing_fields)}"
            )

    def _validate_keyword_collection_schema(self, collection: Any) -> None:
        """校验关键词检索所需字段、Match 能力和 content 索引。"""
        schema_fields = {
            field.name: field
            for field in getattr(collection.schema, "fields", [])
        }
        missing_fields = self.BASE_REQUIRED_FIELDS - set(schema_fields)
        if missing_fields:
            raise RetrievalValidationError(
                "Milvus collection schema mismatch, missing fields: "
                f"{sorted(missing_fields)}"
            )

        content_field = schema_fields["content"]
        field_params = getattr(content_field, "params", None) or {}
        enable_match = (
            getattr(content_field, "enable_match", None) is True
            or str(field_params.get("enable_match", "")).lower() in {"true", "1"}
        )
        if not enable_match:
            raise RetrievalValidationError(
                "Milvus collection content field does not support TEXT_MATCH"
            )

        has_content_index = any(
            getattr(index, "field_name", None) == "content"
            for index in (getattr(collection, "indexes", None) or [])
        )
        if not has_content_index:
            raise RetrievalValidationError(
                "Milvus collection content index not found"
            )

    @classmethod
    def _score_metadata_headers(cls, *, query: str, metadata: Any) -> float:
        """按 query token 覆盖率计算 metadata 标题路径匹配分。"""
        query_tokens = cls._mixed_tokens(query)
        if not query_tokens:
            return 0.0

        header_values = cls._extract_header_values(metadata)
        if not header_values:
            return 0.0

        # 只统计命中的 token 数，不再因为连续命中额外加分。
        # 这样长文件名或大标题只命中 query 的一部分时，不会被直接抬到极高分。
        header_path_tokens = cls._mixed_tokens(" ".join(header_values))
        coverage = cls._multiset_overlap_count(query_tokens, header_path_tokens) / len(query_tokens)
        return min(coverage, 1.0)

    @staticmethod
    def _extract_header_values(metadata: Any) -> list[str]:
        """从 metadata 中按标题层级提取字符串，用于标题相关性评分。

        file_name is prepended as the highest-priority value so that queries
        mentioning a specific document name can distinguish same-title chunks
        from different documents.
        """
        if not isinstance(metadata, dict):
            return []

        values: list[str] = []

        # --- file_name (highest priority, placed first) ---
        file_name = metadata.get("file_name")
        if isinstance(file_name, str) and file_name.strip():
            values.append(file_name.strip())

        # --- headers (h1/h2/h3 hierarchy, stable order) ---
        headers = metadata.get("headers")
        if isinstance(headers, dict):
            sorted_items = sorted(
                headers.items(),
                key=lambda item: MilvusRetrievalStore._header_sort_key(item[0]),
            )
            for _, header_value in sorted_items:
                stripped = str(header_value).strip()
                if stripped:
                    values.append(stripped)

        return values

    @staticmethod
    def _header_sort_key(header_key: Any) -> tuple[int, str]:
        """优先按 h1、h2 等标题层级排序，无法识别时按字典序排序。"""
        key_text = str(header_key).strip().lower()
        match = re.fullmatch(r"h(\d+)", key_text)
        if match:
            return int(match.group(1)), key_text
        return 10_000, key_text

    @staticmethod
    def _mixed_tokens(text: str) -> list[str]:
        """将中英文混合文本切分为用于标题匹配的词元。"""
        tokens: list[str] = []
        current: list[str] = []
        current_kind: str | None = None

        def flush_current() -> None:
            """将当前 ASCII 单词或数字缓冲区写入词元列表。"""
            nonlocal current, current_kind
            if current:
                tokens.append("".join(current).lower())
            current = []
            current_kind = None

        for char in text:
            if re.match(r"[A-Za-z]", char):
                char_kind = "alpha"
            elif re.match(r"[0-9]", char):
                char_kind = "digit"
            elif "\u4e00" <= char <= "\u9fff":
                flush_current()
                tokens.append(char)
                continue
            else:
                # Punctuation, spaces, and unsupported symbols are separators.
                flush_current()
                continue

            if current_kind not in (None, char_kind):
                flush_current()
            current.append(char)
            current_kind = char_kind

        flush_current()
        return tokens

    @staticmethod
    def _multiset_overlap_count(left: list[str], right: list[str]) -> int:
        """按照保留重复项的多重集合语义计算词元交集数量。"""
        left_counter = Counter(left)
        right_counter = Counter(right)
        return sum(
            min(left_counter[token], right_counter[token])
            for token in left_counter.keys() & right_counter.keys()
        )

    @staticmethod
    def _build_output_fields(collection: Any) -> list[str]:
        """构建 output_fields，若 Collection schema 存在 metadata 字段则一并读取。"""
        fields = ["content", "source", "chunk_id", "file_id", "chunk_index"]
        schema_field_names = {
            field.name for field in getattr(collection.schema, "fields", [])
        }
        if "metadata" in schema_field_names:
            fields.append("metadata")
        return fields

    @staticmethod
    def _build_file_filter(file_ids: list[str]) -> str | None:
        """将已校验的文件 ID 安全转换为 Milvus 过滤表达式。"""
        if not file_ids:
            return None
        # json.dumps 会正确转义引号和反斜线，避免原始字符串破坏过滤表达式。
        serialized_ids = ", ".join(
            json.dumps(file_id, ensure_ascii=False)
            for file_id in file_ids
        )
        return f"file_id in [{serialized_ids}]"

    @classmethod
    def _build_keyword_expression(
        cls,
        *,
        query: str,
        file_ids: list[str],
    ) -> str:
        """安全构造 TEXT_MATCH 与可选 file_id 过滤表达式。"""
        # 使用 JSON 字符串编码转义引号和反斜线，避免查询文本破坏 Milvus 表达式。
        serialized_query = json.dumps(query, ensure_ascii=False)
        match_expression = f"TEXT_MATCH(content, {serialized_query})"
        file_filter = cls._build_file_filter(file_ids)
        if file_filter:
            return f"({file_filter}) and ({match_expression})"
        return match_expression

    @staticmethod
    def _build_chunk(
        *,
        hit: Any,
        score: float,
        collection_name: str,
    ) -> RetrievalChunk:
        """从 Milvus Hit 中提取并校验稳定 Chunk 字段。"""
        return MilvusRetrievalStore._build_chunk_from_values(
            values=hit.entity,
            score=score,
            collection_name=collection_name,
        )

    @staticmethod
    def _build_chunk_from_values(
        *,
        values: Any,
        score: float,
        collection_name: str,
    ) -> RetrievalChunk:
        """从 Milvus Hit Entity 或 Query 字典构造稳定 Chunk。"""
        raw_metadata = values.get("metadata")
        values = {
            "collection_name": collection_name,
            "chunk_id": values.get("chunk_id"),
            "file_id": values.get("file_id"),
            "source": values.get("source"),
            "chunk_index": values.get("chunk_index"),
            "content": values.get("content"),
        }
        missing = sorted(key for key, value in values.items() if value is None)
        if missing:
            raise RetrievalValidationError(
                f"Milvus search result missing fields: {missing}"
            )
        try:
            return RetrievalChunk(
                collection_name=str(values["collection_name"]),
                chunk_id=str(values["chunk_id"]),
                file_id=str(values["file_id"]),
                source=str(values["source"]),
                chunk_index=int(values["chunk_index"]),
                content=str(values["content"]),
                score=score,
                metadata=raw_metadata if isinstance(raw_metadata, dict) else None,
            )
        except (TypeError, ValueError) as exc:
            raise RetrievalValidationError(
                f"Milvus search result field type invalid: {exc}"
            ) from exc
    def _disconnect_sync(self) -> None:
        """同步断开 Milvus 连接。"""
        try:
            from pymilvus import connections

            if connections.has_connection(self.connection_alias):
                connections.disconnect(self.connection_alias)
        except ImportError:
            return


# 模块级单例保证 Milvus 连接可跨请求复用。
milvus_store = MilvusRetrievalStore()
