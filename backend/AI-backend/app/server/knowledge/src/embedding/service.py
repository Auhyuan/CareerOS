from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.server.agent.src.model.constants import (
    DEFAULT_MODEL_MAX_RETRIES,
    DEFAULT_MODEL_TIMEOUT_SECONDS,
    MODEL_RETRYABLE_STATUS_CODES,
)
from app.server.agent.src.model.resource import ModelRuntimeResource, resolve_model_resource
from app.server.knowledge.src.config import knowledge_config as settings
from app.server.knowledge.src.logging_config import logger


class EmbeddingService:
    """通过 model_configs 中的 Embedding 模型配置生成向量。"""

    def __init__(self) -> None:
        """创建可复用连接池，模型连接信息在调用时按 model_code 解析。"""
        limits = httpx.Limits(
            max_keepalive_connections=settings.http_max_keepalive_connections,
            max_connections=settings.http_max_connections,
        )
        self._client = httpx.AsyncClient(limits=limits)

    async def close(self) -> None:
        """关闭底层 HTTP 连接池。"""
        await self._client.aclose()

    async def health_check(self, model_code: str) -> int:
        """调用指定 Embedding 模型并校验实际向量维度。"""
        resource = resolve_model_resource(model_code, "embedding")
        vector = await self.embed_text(
            text="embedding service health check",
            model_code=model_code,
        )
        actual_dimension = len(vector)
        if resource.dimension is None:
            raise ValueError(f"Embedding 模型 {model_code} 未配置向量维度")
        if actual_dimension != resource.dimension:
            raise ValueError(
                "embedding health check dimension mismatch: "
                f"expected {resource.dimension}, got {actual_dimension}"
            )
        return actual_dimension

    async def embed_text(
        self,
        text: str,
        model_code: str,
        extra_params: dict[str, Any] | None = None,
        resource: ModelRuntimeResource | None = None,
        timeout_seconds: int = DEFAULT_MODEL_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MODEL_MAX_RETRIES,
    ) -> list[float]:
        """使用知识库绑定的 Embedding model_code 生成单条文本向量。"""
        clean_text = self._normalize_text(text)
        resolved_resource = resource or resolve_model_resource(model_code, "embedding")
        if resolved_resource.model_code != model_code:
            raise ValueError("Embedding model_code 与预解析模型资源不一致")
        payload: dict[str, Any] = {
            "model": resolved_resource.model_name,
            "input": [clean_text],
        }
        if extra_params:
            payload.update(extra_params)

        response = await self._post_embedding_with_retry(
            resource=resolved_resource,
            payload=payload,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        return self._parse_embedding_response(response.json())

    async def _post_embedding_with_retry(
        self,
        *,
        resource: ModelRuntimeResource,
        payload: dict[str, Any],
        timeout_seconds: int,
        max_retries: int,
    ) -> httpx.Response:
        """调用 Embedding 接口，并使用统一模型参数处理重试。"""
        max_attempts = max_retries + 1
        last_error: Exception | None = None
        for attempt_index in range(max_attempts):
            try:
                response = await self._client.post(
                    self._build_endpoint(resource.base_url),
                    json=payload,
                    headers=self._build_headers(resource.api_key),
                    timeout=timeout_seconds,
                )
                response.raise_for_status()
                return response
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not self._should_retry(exc) or attempt_index >= max_attempts - 1:
                    raise
                wait_seconds = min(0.5 * (attempt_index + 1), 3.0)
                logger.warning(
                    "Embedding 模型请求失败，准备重试：model_code=%s attempt=%s/%s wait=%.2fs reason=%s",
                    resource.model_code,
                    attempt_index + 1,
                    max_attempts,
                    wait_seconds,
                    exc,
                )
                await asyncio.sleep(wait_seconds)

        raise RuntimeError("embedding request failed without captured exception") from last_error

    @staticmethod
    def _build_endpoint(base_url: str) -> str:
        """兼容模型地址填写到 /v1 或完整 /embeddings 的形式。"""
        clean_url = base_url.rstrip("/")
        return clean_url if clean_url.endswith("/embeddings") else f"{clean_url}/embeddings"

    @staticmethod
    def _should_retry(exc: Exception) -> bool:
        """判断模型异常是否属于可重试的短暂故障。"""
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in MODEL_RETRYABLE_STATUS_CODES
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
    def _normalize_text(text: str) -> str:
        """校验并清理单条文本输入。"""
        if not isinstance(text, str):
            raise ValueError("text must be string")
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("text cannot be empty")
        return clean_text

    @staticmethod
    def _build_headers(api_key: str | None) -> dict[str, str]:
        """使用模型配置中的 API Key 构造鉴权请求头。"""
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}

    @staticmethod
    def _parse_embedding_response(data: dict[str, Any]) -> list[float]:
        """解析 OpenAI-compatible 单条 Embedding 响应。"""
        items = data.get("data") or []
        if len(items) != 1:
            raise ValueError("embedding response size mismatch")
        item = items[0]
        embedding = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(embedding, list):
            raise ValueError("invalid embedding format in response")
        return [float(value) for value in embedding]


embedding_service = EmbeddingService()
