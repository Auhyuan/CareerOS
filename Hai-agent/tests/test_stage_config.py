import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.common.core.exceptions import BusinessException
from app.server.project.src.schemas.project_schemas import ProjectCreateRequest
from app.server.workflow.src.config.stage_config import get_next_stage_definition
from app.server.workflow.src.schemas.workflow_schemas import NodeAdvanceRequest


class StageConfigTestCase(unittest.TestCase):
    """验证阶段顺序只能由后端注册表控制。"""

    def test_fixed_stage_order(self) -> None:
        """项目准备阶段的下一阶段必须固定为需求确认。"""
        next_stage = get_next_stage_definition("project_preparation")
        self.assertEqual("requirement_confirmation", next_stage.stage_code)
        self.assertEqual("需求确认", next_stage.title)

    def test_final_stage_cannot_advance(self) -> None:
        """最后阶段不能通过通用推进接口继续创建节点。"""
        with self.assertRaises(BusinessException):
            get_next_stage_definition("feedback_revision")

    def test_advance_request_rejects_client_stage_override(self) -> None:
        """前端不能在推进请求中覆盖下一阶段和 Agent。"""
        with self.assertRaises(ValidationError):
            NodeAdvanceRequest(
                node_id=uuid4(),
                expected_result_version=1,
                next_stage_code="arbitrary_stage",
                next_agent_id="arbitrary-agent",
            )

    def test_project_request_rejects_agent_override(self) -> None:
        """前端创建项目时不能指定准备阶段 Agent。"""
        with self.assertRaises(ValidationError):
            ProjectCreateRequest(name="测试项目", preparation_agent_id="arbitrary-agent")


if __name__ == "__main__":
    unittest.main()
