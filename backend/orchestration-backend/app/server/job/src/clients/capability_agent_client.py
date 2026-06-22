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

    def get_agent_template(self, agent_id: str) -> dict[str, Any] | None:
        """
        根据 agent_id 查询能力层 Agent 模板。

        Args:
            agent_id: Agent 模板稳定业务 ID。

        Returns:
            Agent 模板数据；模板不存在时返回 None。

        Raises:
            RuntimeError: HTTP 调用失败、业务返回失败或响应结构异常。
        """
        data = self._post(
            path="/agent/templates/detail",
            payload={"agent_id": agent_id},
            operation_name="查询能力层 Agent 模板",
        )
        if data is None:
            return None
        if not isinstance(data, dict):
            raise RuntimeError("能力层 Agent 模板接口返回 data 结构异常")
        return data

    def run_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        调用能力层通用 Agent 运行接口。

        Args:
            payload: 传给能力层 /agent/run 的运行参数。

        Returns:
            能力层返回的 Agent 运行 data。

        Raises:
            RuntimeError: HTTP 调用失败、业务返回失败或响应结构异常。
        """
        data = self._post(
            path="/agent/run",
            payload=payload,
            operation_name="调用能力层 Agent",
        )
        if not isinstance(data, dict):
            raise RuntimeError("能力层 Agent 接口返回 data 结构异常")
        return data

    def _post(
        self,
        *,
        path: str,
        payload: dict[str, Any],
        operation_name: str,
    ) -> Any:
        """
        调用能力层 POST 接口并解析统一响应。

        Args:
            path: 能力层接口路径。
            payload: POST 请求体。
            operation_name: 用于异常提示的操作名称。

        Returns:
            统一响应中的 data 字段。

        Raises:
            RuntimeError: HTTP 调用失败、响应不是 JSON 或业务 code 非零。
        """
        url = f"{self.config.capability_base_url.rstrip('/')}{path}"

        try:
            with httpx.Client(timeout=self.config.capability_timeout_seconds) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(f"{operation_name}失败: {error}") from error

        try:
            body = response.json()
        except ValueError as error:
            raise RuntimeError(f"{operation_name}返回内容不是合法 JSON") from error

        if not isinstance(body, dict):
            raise RuntimeError(f"{operation_name}返回结构异常")
        if body.get("code") != 0:
            raise RuntimeError(body.get("msg") or f"{operation_name}返回失败")
        return body.get("data")
