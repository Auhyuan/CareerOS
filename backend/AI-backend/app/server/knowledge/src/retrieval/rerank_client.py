"""HTTP Rerank 模型服务客户端。"""

from typing import Any

import httpx

from app.server.knowledge.src.config import knowledge_config as settings
from app.server.knowledge.src.retrieval.schemas import RerankConfig
from app.server.knowledge.src.retrieval.exceptions import RetrievalDependencyError, RetrievalValidationError


class RerankClient:
    """调用 HTTP Rerank 服务并返回候选下标排序。"""

    def __init__(self) -> None:
        """创建可复用的异步 HTTP 连接池。"""
        limits = httpx.Limits(
            max_keepalive_connections=settings.http_max_keepalive_connections,
            max_connections=settings.http_max_connections,
        )
        self._client = httpx.AsyncClient(
            timeout=settings.rerank_timeout,
            limits=limits,
        )

    async def close(self) -> None:
        """关闭 Rerank HTTP 连接池。"""
        await self._client.aclose()

    async def health_check(self) -> int:
        """
        调用 Rerank 服务执行一次真实健康检查。

        Rerank 没有类似 Embedding 向量维度的固定响应，因此使用两个最小候选，
        校验下游能否返回合法的候选下标，并将有效下标数量作为检查结果。
        """
        ordered_indices = await self.rerank(
            query="retrieval rerank health check",
            documents=[
                "retrieval rerank health check document",
                "unrelated candidate document",
            ],
            config=RerankConfig(model_name=settings.rerank_model),
        )
        return len(ordered_indices)

    async def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        config: RerankConfig,
    ) -> list[int]:
        """
        调用 Rerank 服务返回候选排序下标。

        Rerank 服务对齐当前项目模型网关协议：返回 results 数组，每个元素包含原候选 index。
        """
        if not documents:
            return []
        if not settings.rerank_base_url:
            raise RetrievalValidationError("RERANK_BASE_URL is required when rerank is enabled")

        payload = {
            "model": config.model_name or settings.rerank_model,
            "query": query,
            "documents": documents,
        }
        try:
            response = await self._client.post(
                settings.rerank_base_url.rstrip("/"),
                json=payload,
                headers=self._build_headers(),
            )
            response.raise_for_status()
            response_data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RetrievalDependencyError(f"Rerank model request failed: {exc}") from exc

        return self._parse_response(
            response_data=response_data,
            document_count=len(documents),
        )

    @staticmethod
    def _parse_response(
        *,
        response_data: dict[str, Any],
        document_count: int,
    ) -> list[int]:
        """校验 Rerank 响应并提取合法候选下标。"""
        results = response_data.get("results") if isinstance(response_data, dict) else None
        if not isinstance(results, list):
            raise RetrievalDependencyError("Rerank model response missing results")

        ordered_indices: list[int] = []
        seen_indices: set[int] = set()
        for item in results:
            index = item.get("index") if isinstance(item, dict) else None
            if not isinstance(index, int):
                continue
            if index < 0 or index >= document_count or index in seen_indices:
                continue
            ordered_indices.append(index)
            seen_indices.add(index)

        if not ordered_indices:
            raise RetrievalDependencyError("Rerank model response has no valid index")

        # 下游可能只返回部分下标；未返回的候选按原始顺序追加，避免候选丢失。
        for index in range(document_count):
            if index not in seen_indices:
                ordered_indices.append(index)
        return ordered_indices

    @staticmethod
    def _build_headers() -> dict[str, str]:
        """根据本地配置构造 Rerank 服务鉴权请求头。"""
        if not settings.rerank_api_key:
            return {}
        return {"Authorization": f"Bearer {settings.rerank_api_key}"}


# 模块级单例供业务请求和关闭阶段复用。
rerank_client = RerankClient()
