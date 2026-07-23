"""MCP Runtime Context 自动注入测试。"""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from langchain_mcp_adapters.interceptors import MCPToolCallRequest

from app.server.agent.src.mcp.client import (
    MCPConnectionConfig,
    create_multi_server_client,
)
from app.server.agent.src.mcp.runtime_context_interceptor import (
    MCPRuntimeContextInterceptor,
    RUN_ID_HEADER,
    RUNTIME_CONTEXT_TOOL_HEADERS,
)


class MCPRuntimeContextInterceptorTestCase(unittest.IsolatedAsyncioTestCase):
    """验证 MCP 工具运行上下文的白名单请求头透传。"""

    @staticmethod
    def _build_runtime() -> tuple[SimpleNamespace, dict[str, object]]:
        """构造包含 Hai-agent 工作流标识的 LangGraph Runtime。"""
        values: dict[str, object] = {
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "branch_id": str(uuid4()),
            "node_id": str(uuid4()),
            "stage_code": "project_preparation",
            "expected_result_version": 0,
        }
        context = SimpleNamespace(inputs=values, run_id="run-test")
        return SimpleNamespace(context=context), values

    async def test_injects_context_headers_for_stage_result_tool(self) -> None:
        """save_stage_result 调用应自动携带白名单业务请求头。"""
        runtime, values = self._build_runtime()
        interceptor = MCPRuntimeContextInterceptor()
        captured_request = None

        async def handler(request):
            """捕获拦截器传给远程 MCP 执行器的请求。"""
            nonlocal captured_request
            captured_request = request
            return "ok"

        result = await interceptor(
            MCPToolCallRequest(
                name="save_stage_result",
                args={"result": {"goal": "新品发布"}},
                server_name="hai-agent",
                runtime=runtime,
            ),
            handler,
        )

        self.assertEqual(result, "ok")
        self.assertIsNotNone(captured_request)
        for field, header_name in RUNTIME_CONTEXT_TOOL_HEADERS["save_stage_result"].items():
            self.assertEqual(captured_request.headers[header_name], str(values[field]))
        self.assertEqual(captured_request.headers[RUN_ID_HEADER], "run-test")

    async def test_other_mcp_tools_are_not_given_runtime_context(self) -> None:
        """未声明上下文需求的普通 MCP 工具必须保持原始请求。"""
        interceptor = MCPRuntimeContextInterceptor()
        original_request = MCPToolCallRequest(
            name="search_job_skills",
            args={"keywords": ["Python"]},
            server_name="orchestration",
            runtime=None,
        )

        async def handler(request):
            """直接返回处理器收到的 MCP 请求。"""
            return request

        handled_request = await interceptor(original_request, handler)
        self.assertIs(handled_request, original_request)
        self.assertIsNone(handled_request.headers)

    async def test_missing_runtime_field_is_rejected_before_remote_call(self) -> None:
        """缺少节点上下文时不能向远程 MCP 服务发送不完整请求。"""
        runtime, _ = self._build_runtime()
        del runtime.context.inputs["node_id"]
        interceptor = MCPRuntimeContextInterceptor()

        async def handler(request):
            """该处理器不应在上下文校验失败时被调用。"""
            self.fail("上下文缺失时不应执行远程 MCP 工具")

        with self.assertRaises(RuntimeError):
            await interceptor(
                MCPToolCallRequest(
                    name="save_stage_result",
                    args={"result": {}},
                    server_name="hai-agent",
                    runtime=runtime,
                ),
                handler,
            )

    def test_multi_server_client_installs_runtime_interceptor(self) -> None:
        """所有动态加载的 MCP 工具客户端都应安装运行上下文拦截器。"""
        client = create_multi_server_client([
            MCPConnectionConfig(
                key="hai_agent",
                base_url="http://127.0.0.1:8093/mcp/",
            )
        ])
        self.assertTrue(
            any(isinstance(item, MCPRuntimeContextInterceptor) for item in client.tool_interceptors)
        )


if __name__ == "__main__":
    unittest.main()
