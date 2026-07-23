"""解析 AI-backend 随 MCP 请求传入的可信运行上下文。"""

from dataclasses import dataclass
from uuid import UUID

import jwt
from fastmcp.server.dependencies import get_http_headers
from jwt import InvalidTokenError

from app.common.config.settings import get_settings
from app.common.core.exceptions import BusinessException


RUNTIME_CONTEXT_HEADER = "x-agent-runtime-context"


@dataclass(frozen=True)
class MCPRuntimeContext:
    """保存 MCP 工具执行所需的可信业务标识。"""

    user_id: UUID
    project_id: UUID
    branch_id: UUID
    node_id: UUID
    stage_code: str
    expected_result_version: int
    run_id: str | None = None


def get_mcp_runtime_context() -> MCPRuntimeContext:
    """从当前 MCP HTTP 请求读取并验证签名运行上下文。"""
    headers = get_http_headers(include_all=True)
    token = str(headers.get(RUNTIME_CONTEXT_HEADER) or "").strip()
    if not token:
        raise BusinessException(401, f"MCP 请求缺少 {RUNTIME_CONTEXT_HEADER} 请求头")
    return decode_mcp_runtime_context(token)


def decode_mcp_runtime_context(token: str) -> MCPRuntimeContext:
    """验证运行上下文 JWT，并转换为强类型业务上下文。"""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.mcp_runtime_context_secret,
            algorithms=[settings.mcp_runtime_context_algorithm],
            issuer=settings.mcp_runtime_context_issuer,
            audience=settings.mcp_runtime_context_audience,
        )
        if payload.get("type") != "mcp_runtime_context":
            raise BusinessException(401, "MCP 运行上下文令牌类型不正确")

        stage_code = str(payload["stage_code"]).strip()
        if not stage_code:
            raise BusinessException(401, "MCP 运行上下文缺少有效阶段编码")

        expected_version = int(payload["expected_result_version"])
        if expected_version < 0:
            raise BusinessException(401, "MCP 运行上下文结果版本不能小于 0")

        return MCPRuntimeContext(
            user_id=UUID(str(payload["user_id"])),
            project_id=UUID(str(payload["project_id"])),
            branch_id=UUID(str(payload["branch_id"])),
            node_id=UUID(str(payload["node_id"])),
            stage_code=stage_code,
            expected_result_version=expected_version,
            run_id=str(payload.get("run_id") or "").strip() or None,
        )
    except BusinessException:
        raise
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise BusinessException(401, "MCP 运行上下文无效或已过期") from error
