"""节点 Agent 消息 API 测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.common.db.postgres import get_db_session
from app.main import create_app
from app.server.auth.src.dependencies import get_current_user
from app.server.workflow.src.service.node_agent_service import PreparedNodeAgentMessage


class NodeAgentApiTestCase(unittest.TestCase):
    """验证节点消息入口的统一响应和数据库事务释放。"""

    def test_non_stream_message_returns_unified_result(self) -> None:
        """非流式调用应返回节点信息和 AI-backend 最终输出。"""
        app = create_app()
        user_id = uuid4()
        node_id = uuid4()
        db = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user_id=user_id)
        app.dependency_overrides[get_db_session] = lambda: db

        prepared = PreparedNodeAgentMessage(
            node_id=node_id,
            agent_id="hai-project-preparation-agent",
            conversation_id="hai:test:thread",
            payload={"stream": False, "message": "整理项目资料"},
        )
        prepared_service = MagicMock()
        prepared_service.prepare_message.return_value = prepared
        upstream_client = MagicMock()
        upstream_client.run_message = AsyncMock(
            return_value={
                "run_id": "run-1",
                "answer": "项目准备信息已整理",
                "tool_results": [{"tool_name": "save_stage_result"}],
            }
        )

        with (
            patch(
                "app.server.workflow.api.workflow_api.node_agent_service",
                prepared_service,
            ),
            patch(
                "app.server.workflow.api.workflow_api.ai_backend_agent_client",
                upstream_client,
            ),
        ):
            response = TestClient(app).post(
                "/workflow/nodes/messages",
                json={
                    "node_id": str(node_id),
                    "message": "整理项目资料",
                    "stream": False,
                },
            )

        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["node_id"], str(node_id))
        self.assertEqual(body["data"]["run_id"], "run-1")
        self.assertEqual(body["data"]["answer"], "项目准备信息已整理")
        db.rollback.assert_called_once()
        upstream_client.run_message.assert_awaited_once_with(prepared.payload)


if __name__ == "__main__":
    unittest.main()
