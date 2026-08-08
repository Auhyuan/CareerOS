"""Hai-agent 节点会话 ID 生成规则测试。"""

import unittest
from uuid import UUID

from app.server.project.src.service.project_service import ProjectService
from app.server.workflow.src.service.workflow_service import WorkflowService


class ThreadIdTestCase(unittest.TestCase):
    """验证项目根节点、推进节点和分支节点使用短 UUID 会话 ID。"""

    def test_project_thread_id_is_standard_uuid(self) -> None:
        """项目服务生成的 thread_id 应为 36 位标准 UUID。"""
        thread_id = ProjectService._build_thread_id()

        self.assertEqual(str(UUID(thread_id)), thread_id)
        self.assertEqual(len(thread_id), 36)

    def test_workflow_thread_id_is_standard_uuid(self) -> None:
        """工作流服务生成的 thread_id 应为 36 位标准 UUID。"""
        thread_id = WorkflowService._build_thread_id()

        self.assertEqual(str(UUID(thread_id)), thread_id)
        self.assertEqual(len(thread_id), 36)

    def test_each_node_receives_an_independent_thread_id(self) -> None:
        """连续创建节点时必须生成互不复用的会话 ID。"""
        self.assertNotEqual(
            WorkflowService._build_thread_id(),
            WorkflowService._build_thread_id(),
        )


if __name__ == "__main__":
    unittest.main()
