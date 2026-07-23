"""工作流节点 Agent 上下文组装测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.common.core.exceptions import BusinessException
from app.server.workflow.src.schemas.workflow_schemas import NodeAgentMessageRequest
from app.server.workflow.src.service.node_agent_service import NodeAgentService


class NodeAgentServiceTestCase(unittest.TestCase):
    """验证节点归属、动态提示词变量和 MCP Runtime Context 参数。"""

    @staticmethod
    def _build_models():
        """构造一个需求确认阶段的项目和节点。"""
        project_id = uuid4()
        branch_id = uuid4()
        node_id = uuid4()
        project = SimpleNamespace(
            project_id=project_id,
            name="新品发布会",
            customer_name="示例客户",
            brand_name="示例品牌",
            event_type="发布会",
            description="面向渠道伙伴发布新品",
            metadata_json={"city": "深圳"},
            status="active",
        )
        node = SimpleNamespace(
            node_id=node_id,
            project_id=project_id,
            branch_id=branch_id,
            stage_code="requirement_confirmation",
            status="working",
            input_context={
                "completed_stage": "project_preparation",
                "stage_results": {
                    "project_preparation": {"activity_goal": "新品发布"}
                },
            },
            result_data={"open_questions": ["预算范围"]},
            result_version=2,
            agent_id="hai-requirement-confirmation-agent",
            agent_thread_id=f"hai:{project_id}:{node_id}:thread",
        )
        return project, node

    def test_prepare_message_builds_trusted_runtime_inputs(self) -> None:
        """节点消息应包含模板渲染和 MCP 保存所需的完整上下文。"""
        project, node = self._build_models()
        repository = MagicMock()
        repository.get_owned_node_context.return_value = (node, project)
        service = NodeAgentService(repository=repository)
        user_id = uuid4()
        knowledge_id = uuid4()

        prepared = service.prepare_message(
            MagicMock(),
            user_id,
            NodeAgentMessageRequest(
                node_id=node.node_id,
                message="预算暂定 30 万",
                stream=True,
                file_ids=["file-1", "file-1"],
                knowledge_base_ids=[knowledge_id, knowledge_id],
            ),
        )

        payload = prepared.payload
        inputs = payload["inputs"]
        self.assertEqual(payload["agent_id"], node.agent_id)
        self.assertEqual(payload["conversation_id"], node.agent_thread_id)
        self.assertEqual(payload["file_ids"], ["file-1"])
        self.assertEqual(payload["knowledge"]["knowledge_base_ids"], [str(knowledge_id)])
        self.assertEqual(inputs["user_id"], str(user_id))
        self.assertEqual(inputs["project_id"], str(project.project_id))
        self.assertEqual(inputs["branch_id"], str(node.branch_id))
        self.assertEqual(inputs["node_id"], str(node.node_id))
        self.assertEqual(inputs["stage_code"], node.stage_code)
        self.assertEqual(inputs["expected_result_version"], 2)
        self.assertEqual(
            inputs["previous_stage_result"],
            {"activity_goal": "新品发布"},
        )
        self.assertEqual(
            inputs["current_stage_result"],
            {"open_questions": ["预算范围"]},
        )
        self.assertEqual(inputs["project_context"]["project_name"], "新品发布会")

    def test_completed_node_cannot_start_new_agent_run(self) -> None:
        """已完成节点必须通过分支机制继续，不能直接追加 Agent 对话。"""
        project, node = self._build_models()
        node.status = "completed"
        repository = MagicMock()
        repository.get_owned_node_context.return_value = (node, project)
        service = NodeAgentService(repository=repository)

        with self.assertRaises(BusinessException):
            service.prepare_message(
                MagicMock(),
                uuid4(),
                NodeAgentMessageRequest(node_id=node.node_id, message="继续修改"),
            )

    def test_empty_message_payload_and_files_are_rejected(self) -> None:
        """节点消息不能在没有任何用户输入时启动 Agent。"""
        with self.assertRaises(ValueError):
            NodeAgentMessageRequest(node_id=uuid4())


if __name__ == "__main__":
    unittest.main()
