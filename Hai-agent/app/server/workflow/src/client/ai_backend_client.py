"""封装 Hai-agent 到 AI-backend Agent 服务的 HTTP 调用。"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.common.config.settings import get_settings
from app.common.core.exceptions import BusinessException


logger = logging.getLogger("hai_agent.ai_backend")


class AIBackendAgentClient:
    """复用 HTTP 连接池调用 AI-backend 的统一 Agent 消息接口。"""

    def __init__(self, base_url: str | None = None):
        """初始化 AI-backend 地址，HTTP 客户端在首次调用时延迟创建。"""
        settings = get_settings()
        self.base_url = (base_url or settings.ai_backend_base_url).rstrip("/")
        self._timeout = httpx.Timeout(
            connect=settings.ai_backend_connect_timeout_seconds,
            read=settings.ai_backend_timeout_seconds,
            write=settings.ai_backend_timeout_seconds,
            pool=settings.ai_backend_connect_timeout_seconds,
        )
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """返回进程内复用的异步 HTTP 客户端。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return self._client

    async def close(self) -> None:
        """关闭共享 HTTP 连接池。"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def run_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """以非流式方式执行 Agent，并返回统一响应中的 data。"""
        try:
            response = await self._get_client().post("/agent/messages", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as error:
            logger.exception("AI-backend Agent 非流式调用失败")
            raise BusinessException(502, f"AI-backend Agent 服务不可用: {error}") from error

        body = self._parse_json_response(response)
        if int(body.get("code", 500)) != 0:
            raise BusinessException(502, f"AI-backend Agent 调用失败: {body.get('msg') or '未知错误'}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise BusinessException(502, "AI-backend Agent 返回缺少有效 data")
        return data

    async def stream_message(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        """流式调用 Agent，并把上游 SSE 事件原样转发给前端。"""
        try:
            async with self._get_client().stream(
                "POST",
                "/agent/messages",
                json=payload,
                headers={"Accept": "text/event-stream"},
            ) as response:
                if response.status_code >= 400:
                    content = (await response.aread()).decode("utf-8", errors="replace")
                    yield self._build_error_event(
                        f"AI-backend Agent HTTP {response.status_code}: {content[:500]}"
                    )
                    return

                content_type = response.headers.get("content-type", "").lower()
                if "text/event-stream" not in content_type:
                    body_bytes = await response.aread()
                    yield self._build_non_sse_error_event(response, body_bytes)
                    return

                async for chunk in response.aiter_text():
                    if chunk:
                        yield chunk
        except httpx.HTTPError as error:
            logger.exception("AI-backend Agent 流式调用失败")
            yield self._build_error_event(f"AI-backend Agent 服务不可用: {error}")

    @staticmethod
    def _parse_json_response(response: httpx.Response) -> dict[str, Any]:
        """解析 AI-backend 统一 JSON 响应。"""
        try:
            body = response.json()
        except ValueError as error:
            raise BusinessException(502, "AI-backend Agent 返回内容不是合法 JSON") from error
        if not isinstance(body, dict):
            raise BusinessException(502, "AI-backend Agent 返回格式不正确")
        return body

    @classmethod
    def _build_non_sse_error_event(
        cls,
        response: httpx.Response,
        body_bytes: bytes,
    ) -> str:
        """把上游非 SSE 响应转换为前端可识别的错误事件。"""
        try:
            body = json.loads(body_bytes.decode("utf-8"))
            message = str(body.get("msg") or body)
        except (UnicodeDecodeError, ValueError, AttributeError):
            message = body_bytes.decode("utf-8", errors="replace")[:500]
        return cls._build_error_event(
            f"AI-backend 未返回 SSE 流: HTTP {response.status_code}, {message}"
        )

    @staticmethod
    def _build_error_event(message: str) -> str:
        """构造符合平台流式协议的 SSE 错误事件。"""
        event = {
            "type": "error",
            "data": {
                "code": 502,
                "message": message,
            },
        }
        return "event: error\ndata: " + json.dumps(event, ensure_ascii=False) + "\n\n"
