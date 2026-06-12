from typing import Any, TypedDict


class AgentGraphState(TypedDict, total=False):
    """通用 Agent 图状态定义。"""

    query: str
    inputs: dict[str, Any]
    messages: list[Any]
    structured_output: dict[str, Any]
    metadata: dict[str, Any]
