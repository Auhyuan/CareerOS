from typing import Any

import httpx

from app.server.job.src.config.capability_config import CapabilityBackendConfig, get_capability_backend_config


class CapabilitySpiderClient:
    """能力层爬虫接口客户端。"""

    def __init__(self, config: CapabilityBackendConfig | None = None):
        """
        初始化能力层爬虫客户端。

        Args:
            config: 能力层调用配置；默认从环境变量读取。
        """
        self.config = config or get_capability_backend_config()

    def crawl_qcwy_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        调用能力层前程无忧岗位采集接口。

        Args:
            payload: 传给能力层 `/spider/qcwy/jobs` 的采集参数。

        Returns:
            能力层返回的 data 数据。

        Raises:
            RuntimeError: 能力层 HTTP 调用失败，或能力层返回非成功 code。
        """
        url = f"{self.config.capability_base_url.rstrip('/')}/spider/qcwy/jobs"

        # 爬虫可能需要打开浏览器并等待招聘接口响应，所以这里使用独立的较长超时时间。
        with httpx.Client(timeout=self.config.capability_timeout_seconds) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()

        body = response.json()
        if body.get("code") != 0:
            raise RuntimeError(body.get("msg") or "能力层爬虫接口返回失败")

        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("能力层爬虫接口返回 data 结构异常")
        return data
