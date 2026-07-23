"""AI-backend Agent HTTP 客户端测试。"""

import unittest

import httpx

from app.common.core.exceptions import BusinessException
from app.server.workflow.src.client.ai_backend_client import AIBackendAgentClient


class AIBackendAgentClientTestCase(unittest.IsolatedAsyncioTestCase):
    """验证非流式统一响应解析和 SSE 原样转发。"""

    async def test_run_message_returns_upstream_data(self) -> None:
        """非流式成功响应应只返回 AI-backend 的 data。"""
        async def handler(request: httpx.Request) -> httpx.Response:
            """返回模拟的 AI-backend 统一成功响应。"""
            self.assertEqual(request.url.path, "/agent/messages")
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "success",
                    "data": {"run_id": "run-1", "answer": "已整理", "tool_results": []},
                },
            )

        client = AIBackendAgentClient(base_url="http://ai-backend.test")
        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )
        try:
            result = await client.run_message({"stream": False, "message": "开始"})
        finally:
            await client.close()

        self.assertEqual(result["run_id"], "run-1")
        self.assertEqual(result["answer"], "已整理")

    async def test_run_message_rejects_upstream_business_error(self) -> None:
        """AI-backend 业务错误不能被 Hai-agent 包装成成功结果。"""
        async def handler(request: httpx.Request) -> httpx.Response:
            """返回模拟的 AI-backend 业务失败响应。"""
            return httpx.Response(200, json={"code": 404, "msg": "Agent 模板不存在", "data": None})

        client = AIBackendAgentClient(base_url="http://ai-backend.test")
        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )
        try:
            with self.assertRaises(BusinessException):
                await client.run_message({"stream": False, "message": "开始"})
        finally:
            await client.close()

    async def test_stream_message_forwards_sse_content(self) -> None:
        """流式调用应保留 AI-backend 的事件类型和事件数据。"""
        sse_content = 'event: model_delta\ndata: {"type":"model_delta","data":{"content":"你好"}}\n\n'

        async def handler(request: httpx.Request) -> httpx.Response:
            """返回模拟的 AI-backend SSE 响应。"""
            return httpx.Response(
                200,
                text=sse_content,
                headers={"content-type": "text/event-stream; charset=utf-8"},
            )

        client = AIBackendAgentClient(base_url="http://ai-backend.test")
        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )
        try:
            chunks = [chunk async for chunk in client.stream_message({"stream": True})]
        finally:
            await client.close()

        self.assertEqual("".join(chunks), sse_content)


if __name__ == "__main__":
    unittest.main()
