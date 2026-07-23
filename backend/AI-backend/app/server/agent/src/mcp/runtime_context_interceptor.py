"""为指定 MCP 工具自动注入 Agent Runtime Context 请求头。"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_mcp_adapters.interceptors import (
    MCPToolCallRequest,
    MCPToolCallResult,
)


RUNTIME_CONTEXT_TOOL_HEADERS: dict[str, dict[str, str]] = {
    "save_stage_result": {
        "user_id": "X-Agent-User-Id",
        "project_id": "X-Agent-Project-Id",
        "branch_id": "X-Agent-Branch-Id",
        "node_id": "X-Agent-Node-Id",
        "stage_code": "X-Agent-Stage-Code",
        "expected_result_version": "X-Agent-Expected-Result-Version",
    },
}
RUN_ID_HEADER = "X-Agent-Run-Id"


class MCPRuntimeContextInterceptor:
    """在指定 MCP 工具调用前注入内部业务上下文。

    模型只生成 MCP 工具公开参数。项目、节点和用户归属等字段从
    LangGraph ToolRuntime.context.inputs 读取，并作为内部 HTTP 请求头传入 MCP 服务。
    """

    async def __call__(
        self,
        request: MCPToolCallRequest,
        handler: Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]],
    ) -> MCPToolCallResult:
        """为需要业务上下文的工具写入请求头后继续执行。"""
        header_mapping = RUNTIME_CONTEXT_TOOL_HEADERS.get(request.name)
        if not header_mapping:
            return await handler(request)

        context = self._get_runtime_context(request)
        inputs = self._get_context_inputs(context)
        missing_fields = [
            field for field in header_mapping if inputs.get(field) in (None, "")
        ]
        if missing_fields:
            raise RuntimeError(
                f"MCP 工具 {request.name} 缺少 Runtime Context inputs: "
                + ", ".join(missing_fields)
            )

        # 只注入该工具声明过的白名单字段，避免把整个 inputs 透传给外部服务。
        headers = dict(request.headers or {})
        for field, header_name in header_mapping.items():
            headers[header_name] = str(inputs[field])

        run_id = self._get_context_value(context, "run_id")
        if run_id not in (None, ""):
            headers[RUN_ID_HEADER] = str(run_id)

        return await handler(request.override(headers=headers))

    @staticmethod
    def _get_runtime_context(request: MCPToolCallRequest) -> Any:
        """从适配器工具请求中取得 LangGraph Runtime Context。"""
        runtime = request.runtime
        context = getattr(runtime, "context", None) if runtime is not None else None
        if context is None:
            raise RuntimeError(
                f"MCP 工具 {request.name} 依赖 Agent Runtime Context，不能脱离 Agent 运行直接调用"
            )
        return context

    @staticmethod
    def _get_context_inputs(context: Any) -> dict[str, Any]:
        """兼容字典和 Pydantic Context，提取业务 inputs。"""
        if isinstance(context, dict):
            inputs = context.get("inputs")
        elif hasattr(context, "model_dump"):
            inputs = context.model_dump().get("inputs")
        else:
            inputs = getattr(context, "inputs", None)
        return dict(inputs) if isinstance(inputs, dict) else {}

    @staticmethod
    def _get_context_value(context: Any, key: str) -> Any:
        """从字典或对象形式 Context 读取普通运行字段。"""
        if isinstance(context, dict):
            return context.get(key)
        if hasattr(context, "model_dump"):
            return context.model_dump().get(key)
        return getattr(context, key, None)
