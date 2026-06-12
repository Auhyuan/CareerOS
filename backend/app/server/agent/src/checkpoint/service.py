from typing import Any


class AgentCheckpointService:
    """Agent checkpoint 服务占位实现。"""

    async def get_checkpointer(self) -> Any:
        """
        获取 LangGraph checkpointer。

        Returns:
            当前阶段返回 None；后续接入 PostgreSQL checkpointer。
        """
        return None
