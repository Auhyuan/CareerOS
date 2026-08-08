"""解析 AI-backend 随 MCP 请求透传的完整 Agent inputs。"""

import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastmcp.server.dependencies import get_http_headers

from app.common.core.exceptions import BusinessException


RUNTIME_INPUTS_HEADER = "x-agent-runtime-inputs"
RUN_ID_HEADER = "x-agent-run-id"


@dataclass(frozen=True)
class MCPRuntimeContext:
    """保存 MCP 工具可按需读取的完整 Agent inputs。"""

    inputs: dict[str, Any]
    run_id: str | None = None

    def require(self, key: str) -> Any:
        """读取必填字段；字段不存在或为空时返回清晰的业务错误。"""
        value = self.inputs.get(key)
        if value in (None, ""):
            raise BusinessException(401, f"MCP Runtime Context inputs 缺少字段: {key}")
        return value

    def require_uuid(self, key: str) -> UUID:
        """读取并校验一个必填 UUID 字段。"""
        try:
            return UUID(str(self.require(key)))
        except (TypeError, ValueError) as error:
            raise BusinessException(401, f"MCP Runtime Context inputs 字段不是有效 UUID: {key}") from error

    def require_str(self, key: str) -> str:
        """读取并清理一个必填字符串字段。"""
        value = str(self.require(key)).strip()
        if not value:
            raise BusinessException(401, f"MCP Runtime Context inputs 字段不能为空: {key}")
        return value


def get_mcp_runtime_context() -> MCPRuntimeContext:
    """从当前 MCP HTTP 请求读取并解析完整 Agent inputs。"""
    return parse_mcp_runtime_context(get_http_headers(include_all=True))


def decode_runtime_inputs(encoded_inputs: str) -> dict[str, Any]:
    """解码 AI-backend 通过 URL-safe Base64 传入的 inputs JSON。"""
    try:
        payload = base64.urlsafe_b64decode(encoded_inputs.encode("ascii"))
        inputs = json.loads(payload.decode("utf-8"))
    except (binascii.Error, UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise BusinessException(401, "MCP Runtime Context inputs 编码不正确") from error
    if not isinstance(inputs, dict):
        raise BusinessException(401, "MCP Runtime Context inputs 必须是 JSON 对象")
    return inputs


def parse_mcp_runtime_context(headers: Mapping[str, str]) -> MCPRuntimeContext:
    """从统一请求头还原完整 inputs，具体工具自行读取所需字段。"""
    encoded_inputs = str(headers.get(RUNTIME_INPUTS_HEADER) or "").strip()
    if not encoded_inputs:
        raise BusinessException(401, "MCP 请求缺少完整 Runtime Context inputs")

    return MCPRuntimeContext(
        inputs=decode_runtime_inputs(encoded_inputs),
        run_id=str(headers.get(RUN_ID_HEADER) or "").strip() or None,
    )
