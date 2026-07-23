"""解析 AI-backend 随 MCP 请求传入的内部运行上下文。"""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from fastmcp.server.dependencies import get_http_headers

from app.common.core.exceptions import BusinessException


RUNTIME_CONTEXT_HEADERS: dict[str, str] = {
    "user_id": "x-agent-user-id",
    "project_id": "x-agent-project-id",
    "branch_id": "x-agent-branch-id",
    "node_id": "x-agent-node-id",
    "stage_code": "x-agent-stage-code",
    "expected_result_version": "x-agent-expected-result-version",
}
RUN_ID_HEADER = "x-agent-run-id"


@dataclass(frozen=True)
class MCPRuntimeContext:
    """保存 MCP 工具执行所需的内部业务标识。"""

    user_id: UUID
    project_id: UUID
    branch_id: UUID
    node_id: UUID
    stage_code: str
    expected_result_version: int
    run_id: str | None = None


def get_mcp_runtime_context() -> MCPRuntimeContext:
    """从当前 MCP HTTP 请求读取并校验内部运行上下文。"""
    return parse_mcp_runtime_context(get_http_headers(include_all=True))


def parse_mcp_runtime_context(headers: Mapping[str, str]) -> MCPRuntimeContext:
    """把内部请求头转换为强类型 MCP 运行上下文。"""
    missing_fields = [
        field
        for field, header_name in RUNTIME_CONTEXT_HEADERS.items()
        if not str(headers.get(header_name) or "").strip()
    ]
    if missing_fields:
        raise BusinessException(
            401,
            "MCP 请求缺少运行上下文请求头: " + ", ".join(missing_fields),
        )

    try:
        stage_code = str(headers[RUNTIME_CONTEXT_HEADERS["stage_code"]]).strip()
        expected_version = int(
            headers[RUNTIME_CONTEXT_HEADERS["expected_result_version"]]
        )
        if expected_version < 0:
            raise ValueError("结果版本不能小于 0")

        return MCPRuntimeContext(
            user_id=UUID(str(headers[RUNTIME_CONTEXT_HEADERS["user_id"]])),
            project_id=UUID(str(headers[RUNTIME_CONTEXT_HEADERS["project_id"]])),
            branch_id=UUID(str(headers[RUNTIME_CONTEXT_HEADERS["branch_id"]])),
            node_id=UUID(str(headers[RUNTIME_CONTEXT_HEADERS["node_id"]])),
            stage_code=stage_code,
            expected_result_version=expected_version,
            run_id=str(headers.get(RUN_ID_HEADER) or "").strip() or None,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise BusinessException(401, "MCP 运行上下文请求头格式不正确") from error
