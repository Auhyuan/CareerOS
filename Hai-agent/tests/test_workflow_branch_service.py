"""历史节点创建工作流分支的服务测试。"""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.common.core.exceptions import BusinessException
from app.server.workflow.src.models.workflow_models import WorkflowNodeModel
from app.server.workflow.src.schemas.workflow_schemas import BranchCreateRequest
from app.server.workflow.src.service.workflow_service import WorkflowService


class WorkflowBranchServiceTestCase(unittest.TestCase):
    """验证历史节点派生分支时的数据复制、隔离和并发校验。"""

    @staticmethod
    def _build_source_node(*, status: str = "completed", result_version: int = 2) -> WorkflowNodeModel:
        """构造包含稳定阶段结果的历史节点。"""
        return WorkflowNodeModel(
            node_id=uuid4(),
            project_id=uuid4(),
            branch_id=uuid4(),
            parent_node_id=uuid4(),
            sequence_no=2,
            stage_code="requirement_confirmation",
            status=status,
            title="需求确认",
            summary="需求信息已确认",
            input_context={"stage_results": {"project_preparation": {"brief": "已整理"}}},
            result_data={"requirements": {"budget": "50 万元"}},
            handoff_context={"old": True},
            result_version=result_version,
            agent_id="old-agent",
            agent_thread_id="old-thread",
            checkpoint_id="old-checkpoint",
            created_at=datetime.now(timezone.utc),
        )

    def test_create_branch_copies_business_baseline_and_isolates_checkpoint(self) -> None:
        """新分支应复制业务基线，但重置运行状态、结果版本和 Agent 会话。"""
        repository = MagicMock()
        source = self._build_source_node()
        source_branch = SimpleNamespace(branch_id=source.branch_id, project_id=source.project_id)
        project = SimpleNamespace(
            project_id=source.project_id,
            status="active",
            current_branch_id=source.branch_id,
            current_node_id=source.node_id,
            current_stage=source.stage_code,
        )
        repository.get_owned_node_for_update.return_value = source
        repository.get_branch_for_update.return_value = source_branch
        repository.get_project_for_update.return_value = project
        captured: dict[str, object] = {}

        def capture_graph(db, branch, node) -> None:
            """模拟仓储 flush，并保存待断言的新分支和节点。"""
            now = datetime.now(timezone.utc)
            branch.created_at = now
            node.created_at = now
            captured["branch"] = branch
            captured["node"] = node

        repository.add_branch_with_node.side_effect = capture_graph
        db = MagicMock()
        service = WorkflowService(repository)

        response = service.create_branch_from_node(
            db,
            uuid4(),
            BranchCreateRequest(
                source_node_id=source.node_id,
                branch_name="需求确认方案 B",
                expected_result_version=2,
            ),
        )

        branch = captured["branch"]
        node = captured["node"]
        self.assertEqual(branch.source_branch_id, source.branch_id)
        self.assertEqual(branch.source_node_id, source.node_id)
        self.assertEqual(branch.head_node_id, node.node_id)
        self.assertEqual(node.parent_node_id, source.node_id)
        self.assertEqual(node.sequence_no, source.sequence_no)
        self.assertEqual(node.stage_code, source.stage_code)
        self.assertEqual(node.status, "working")
        self.assertEqual(node.result_version, 0)
        self.assertEqual(node.result_data, source.result_data)
        self.assertIsNot(node.result_data, source.result_data)
        self.assertEqual(node.input_context, source.input_context)
        self.assertIsNot(node.input_context, source.input_context)
        self.assertEqual(node.handoff_context, {})
        self.assertIsNone(node.checkpoint_id)
        self.assertNotEqual(node.agent_thread_id, source.agent_thread_id)
        self.assertEqual(project.current_branch_id, branch.branch_id)
        self.assertEqual(project.current_node_id, node.node_id)
        self.assertEqual(response.branch.branch_id, branch.branch_id)
        self.assertEqual(response.node.node_id, node.node_id)
        db.commit.assert_called_once()

    def test_create_branch_rejects_stale_result_version(self) -> None:
        """来源结果版本变化后必须拒绝使用旧版本创建分支。"""
        repository = MagicMock()
        source = self._build_source_node(result_version=3)
        repository.get_owned_node_for_update.return_value = source
        service = WorkflowService(repository)

        with self.assertRaisesRegex(BusinessException, "当前版本为 3"):
            service.create_branch_from_node(
                MagicMock(),
                uuid4(),
                BranchCreateRequest(
                    source_node_id=source.node_id,
                    branch_name="过期分支",
                    expected_result_version=2,
                ),
            )

        repository.add_branch_with_node.assert_not_called()

    def test_create_branch_requires_stable_stage_result(self) -> None:
        """仍在工作的节点没有稳定结果时不能作为分支来源。"""
        repository = MagicMock()
        source = self._build_source_node(status="working")
        repository.get_owned_node_for_update.return_value = source
        service = WorkflowService(repository)

        with self.assertRaisesRegex(BusinessException, "稳定结果"):
            service.create_branch_from_node(
                MagicMock(),
                uuid4(),
                BranchCreateRequest(
                    source_node_id=source.node_id,
                    branch_name="无效分支",
                    expected_result_version=2,
                ),
            )

        repository.add_branch_with_node.assert_not_called()


if __name__ == "__main__":
    unittest.main()
