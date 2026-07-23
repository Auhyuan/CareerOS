from functools import lru_cache

from app.server.workflow.src.client.ai_backend_client import AIBackendAgentClient


@lru_cache(maxsize=1)
def get_ai_backend_agent_client() -> AIBackendAgentClient:
    """返回进程内共享的 AI-backend Agent 客户端。"""
    return AIBackendAgentClient()


async def close_ai_backend_agent_client() -> None:
    """在应用关闭时释放 AI-backend HTTP 连接池。"""
    await get_ai_backend_agent_client().close()


__all__ = [
    "AIBackendAgentClient",
    "get_ai_backend_agent_client",
    "close_ai_backend_agent_client",
]
