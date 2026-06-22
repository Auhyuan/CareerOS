from typing import Any

import httpx

from app.server.job.src.config.capability_config import CapabilityBackendConfig, get_capability_backend_config


class CapabilityAgentClient:
    """能力层 Agent 接口客户端。"""

    def __init__(self, config: CapabilityBackendConfig | None = None):
        """
        初始化能力层 Agent 客户端。
        Args:
            config: 能力层服务调用配置；默认从环境变量读取。
        """
        self.config = config or get_capability_backend_config()

    def run_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        调用能力层通用 Agent 运行接口。
        Args:
            payload: 传给能力层 `/agent/run` 的运行参数。
        Returns:
            能力层返回的 Agent 运行 data。
        Raises:
            RuntimeError: HTTP 调用失败、业务返回失败或响应结构异常。
        """
        url = f"{self.config.capability_base_url.rstrip('/')}/agent/run"

        try:
            with httpx.Client(timeout=self.config.capability_timeout_seconds) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(f"调用能力层 Agent 接口失败: {error}") from error

        try:
            body = response.json()
        except ValueError as error:
            raise RuntimeError("能力层 Agent 接口返回内容不是合法 JSON") from error

        if body.get("code") != 0:
            raise RuntimeError(body.get("msg") or "能力层 Agent 接口返回失败")

        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("能力层 Agent 接口返回 data 结构异常")
        return data
