from typing import Any

import httpx

from app.server.agent.src.tools.job_tools.config import JobToolConfig, get_job_tool_config


class JobToolClient:
    """Job 工具使用的 orchestration-backend HTTP 客户端。"""

    def __init__(
        self,
        config: JobToolConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        """
        初始化 Job 工具 HTTP 客户端。

        Args:
            config: 业务编排层连接配置。
            transport: 测试场景可注入的 httpx 异步传输对象。
        """
        self.config = config or get_job_tool_config()
        self.transport = transport

    async def search_job_skills(self, keyword: str, limit: int = 10) -> dict[str, Any]:
        """
        调用 Job 技能查询接口。

        Args:
            keyword: 技能名称或关键字。
            limit: 最大返回数量。

        Returns:
            Job 接口返回的技能查询数据。
        """
        data = await self._post(
            path="/job/skills/search",
            payload={"keyword": keyword, "limit": limit},
            operation_name="查询岗位技能",
        )
        if not isinstance(data, dict):
            raise RuntimeError("岗位技能查询接口返回 data 结构异常")
        return data

    async def create_job_skill(self, name: str, description: str) -> dict[str, Any]:
        """
        调用 Job 技能创建接口。

        Args:
            name: 技能标准名称。
            description: 技能描述。

        Returns:
            Job 接口返回的技能创建或复用结果。
        """
        data = await self._post(
            path="/job/skills/create",
            payload={"name": name, "description": description},
            operation_name="创建岗位技能",
        )
        if not isinstance(data, dict):
            raise RuntimeError("岗位技能创建接口返回 data 结构异常")
        return data

    async def _post(
        self,
        *,
        path: str,
        payload: dict[str, Any],
        operation_name: str,
    ) -> Any:
        """
        调用业务编排层 POST 接口并解析统一响应。

        Args:
            path: Job 接口路径。
            payload: POST 请求体。
            operation_name: 用于异常提示的操作名称。

        Returns:
            统一响应中的 data 字段。

        Raises:
            RuntimeError: HTTP 调用失败、响应格式异常或业务 code 非零。
        """
        url = f"{self.config.orchestration_base_url.rstrip('/')}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self.config.orchestration_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(f"{operation_name}失败: {error}") from error

        try:
            body = response.json()
        except ValueError as error:
            raise RuntimeError(f"{operation_name}接口返回内容不是合法 JSON") from error

        if not isinstance(body, dict):
            raise RuntimeError(f"{operation_name}接口返回结构异常")
        if body.get("code") != 0:
            raise RuntimeError(body.get("msg") or f"{operation_name}接口返回失败")
        return body.get("data")
