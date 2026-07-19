from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.server.knowledge.src.config import knowledge_config as settings
from app.server.knowledge.src.logging_config import logger


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class EmbeddingService:
    """Embedding 原子能力服务。"""

    def __init__(self) -> None:
        """
        初始化 embedding 服务。

        这里复用一个 AsyncClient，避免每次请求都重新创建连接。
        """
        limits = httpx.Limits(
            max_keepalive_connections=settings.http_max_keepalive_connections,
            max_connections=settings.http_max_connections,
        )
        self._client = httpx.AsyncClient(timeout=settings.embedding_timeout, limits=limits)

    async def close(self) -> None:
        """关闭底层 HTTP 客户端连接池。"""
        await self._client.aclose()

    async def health_check(self) -> int:
        """
        调用下游 embedding 服务执行一次真实健康检查。

        Returns:
            int: 下游模型实际返回的向量维度

        Raises:
            ValueError: 下游返回向量维度与服务配置不一致
            httpx.HTTPError: 下游服务不可访问或返回错误状态码
        """
        vector = await self.embed_text(
            text="embedding service health check",
            model=settings.embedding_model,
        )
        actual_dimension = len(vector)
        if actual_dimension != settings.embedding_dimension:
            raise ValueError(
                "embedding health check dimension mismatch: "
                f"expected {settings.embedding_dimension}, got {actual_dimension}"
            )
        return actual_dimension

    async def embed_text(
        self,
        text: str,
        model: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> list[float]:
        """
        生成单条文本向量。

        Args:
            text: 待向量化文本
            model: 可选模型名称，不传则使用默认模型
            extra_params: 透传给下游 embedding 接口的额外参数

        Returns:
            list[float]: 文本向量
        """
        clean_text = self._normalize_text(text)
        payload: dict[str, Any] = {
            "model": model or settings.embedding_model,
            # OpenAI-compatible embedding 协议使用 input 数组，本服务对外仍只处理单条文本。
            "input": [clean_text],
        }
        if extra_params:
            payload.update(extra_params)

        response = await self._post_embedding_with_retry(payload)
        return self._parse_embedding_response(response.json())

    async def _post_embedding_with_retry(self, payload: dict[str, Any]) -> httpx.Response:
        """请求下游 Embedding 接口，对网关抖动和 5xx 错误做有限重试。"""
        max_attempts = settings.embedding_retry_times + 1
        last_error: Exception | None = None

        for attempt_index in range(max_attempts):
            try:
                response = await self._client.post(
                    settings.embedding_endpoint,
                    json=payload,
                    headers=self._build_headers(),
                )
                response.raise_for_status()
                return response
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not self._should_retry(exc) or attempt_index >= max_attempts - 1:
                    raise

                wait_seconds = self._build_retry_wait_seconds(attempt_index)
                logger.warning(
                    "Embedding 模型请求失败，准备重试：attempt=%s/%s，wait=%.2fs，reason=%s",
                    attempt_index + 1,
                    max_attempts,
                    wait_seconds,
                    exc,
                )
                await asyncio.sleep(wait_seconds)

        # 理论上不会走到这里，保留防御性异常便于排查。
        raise RuntimeError("embedding request failed without captured exception") from last_error

    @staticmethod
    def _should_retry(exc: Exception) -> bool:
        """判断下游异常是否属于可重试的短暂故障。"""
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in _RETRYABLE_STATUS_CODES
        return isinstance(
            exc,
            (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
                httpx.PoolTimeout,
                httpx.RemoteProtocolError,
                httpx.NetworkError,
            ),
        )

    @staticmethod
    def _build_retry_wait_seconds(attempt_index: int) -> float:
        """根据重试轮次生成简单递增等待时间。"""
        return min(0.5 * (attempt_index + 1), 3.0)

    def _normalize_text(self, text: str) -> str:
        """校验并清理单条文本输入。"""
        if not isinstance(text, str):
            raise ValueError("text must be string")
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("text cannot be empty")
        return clean_text

    def _build_headers(self) -> dict[str, str]:
        """构造下游 embedding 请求头。"""
        if not settings.embedding_api_key:
            return {}
        return {"Authorization": f"Bearer {settings.embedding_api_key}"}

    def _parse_embedding_response(self, data: dict[str, Any]) -> list[float]:
        """
        解析单条 OpenAI-compatible embedding 响应。

        预期格式为 {"data": [{"embedding": [...]}]}。
        """
        items = data.get("data") or []
        if len(items) != 1:
            raise ValueError("embedding response size mismatch")

        item = items[0]
        embedding = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(embedding, list):
            raise ValueError("invalid embedding format in response")
        return [float(value) for value in embedding]


# 模块级单例，供路由层复用。
embedding_service = EmbeddingService()
