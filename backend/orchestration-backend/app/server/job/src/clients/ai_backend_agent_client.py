from typing import Any

import httpx

from app.server.job.src.config.ai_backend_config import AIBackendConfig, get_ai_backend_config


class AIBackendAgentClient:
    """AI-backend Agent 服务客户端。"""

    def __init__(self, config: AIBackendConfig | None = None):
        """初始化 AI-backend Agent 客户端。

        Args:
            config: AI-backend 服务配置；不传时从环境变量读取。
        """
        self.config = config or get_ai_backend_config()

    def get_agent_template(self, agent_id: str) -> dict[str, Any] | None:
        """按 agent_id 查询 AI-backend Agent 模板。

        Args:
            agent_id: Agent 模板的唯一 ID。

        Returns:
            Agent 模板配置；不存在时返回 None。

        Raises:
            RuntimeError: HTTP 请求失败、返回格式异常或业务状态码异常时抛出。
        """
        data = self._post(
            path="/agent/templates/detail",
            payload={"agent_id": agent_id},
            operation_name="查询 AI-backend Agent 模板",
        )
        if data is None:
            return None
        if not isinstance(data, dict):
            raise RuntimeError("AI-backend Agent 模板返回的 data 格式异常")
        return data

    def run_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        """调用 AI-backend 执行 Agent。

        Args:
            payload: 发送给 AI-backend /agent/run 的请求体。

        Returns:
            AI-backend 返回的 Agent 执行结果 data。

        Raises:
            RuntimeError: HTTP 请求失败、返回格式异常或业务状态码异常时抛出。
        """
        data = self._post(
            path="/agent/run",
            payload=payload,
            operation_name="调用 AI-backend Agent",
        )
        if not isinstance(data, dict):
            raise RuntimeError("AI-backend Agent 返回的 data 格式异常")
        return data

    def _post(
        self,
        *,
        path: str,
        payload: dict[str, Any],
        operation_name: str,
    ) -> Any:
        """发送 AI-backend POST 请求并解析统一响应。

        Args:
            path: AI-backend 接口路径。
            payload: POST 请求体。
            operation_name: 当前请求的业务操作名称。

        Returns:
            统一响应中的 data 字段。

        Raises:
            RuntimeError: HTTP 请求失败、响应不是 JSON 或 code 非 0 时抛出。
        """
        url = f"{self.config.ai_backend_base_url.rstrip('/')}{path}"

        try:
            # 每次请求使用短生命周期客户端，避免服务间调用残留连接状态。
            with httpx.Client(timeout=self.config.ai_backend_timeout_seconds) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(f"{operation_name}失败: {error}") from error

        try:
            body = response.json()
        except ValueError as error:
            raise RuntimeError(f"{operation_name}返回内容不是合法 JSON") from error

        if not isinstance(body, dict):
            raise RuntimeError(f"{operation_name}返回格式异常")
        if body.get("code") != 0:
            raise RuntimeError(body.get("msg") or f"{operation_name}失败")
        return body.get("data")
