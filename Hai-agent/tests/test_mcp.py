import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.common.core.exceptions import BusinessException
from app.server.mcp.runtime_context import (
    RUNTIME_CONTEXT_HEADERS,
    RUN_ID_HEADER,
    parse_mcp_runtime_context,
)
from app.server.mcp.server import create_mcp_server
from app.server.workflow.src.service.workflow_service import WorkflowService


class MCPRuntimeContextTests(unittest.TestCase):
    """验证 MCP 工具 Schema、请求头上下文和节点边界。"""

    @staticmethod
    def _build_headers(**overrides) -> tuple[dict[str, str], dict[str, str]]:
        """创建测试用 MCP 运行上下文请求头。"""
        values = {
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "branch_id": str(uuid4()),
            "node_id": str(uuid4()),
            "stage_code": "project_preparation",
            "expected_result_version": "0",
        }
        values.update({key: str(value) for key, value in overrides.items()})
        headers = {
            header_name: values[field]
            for field, header_name in RUNTIME_CONTEXT_HEADERS.items()
        }
        headers[RUN_ID_HEADER] = "test-run"
        return headers, values

    def test_parse_runtime_context_headers(self) -> None:
        """有效请求头应完整还原强类型业务上下文。"""
        headers, values = self._build_headers()
        context = parse_mcp_runtime_context(headers)

        self.assertEqual(str(context.user_id), values["user_id"])
        self.assertEqual(str(context.project_id), values["project_id"])
        self.assertEqual(str(context.node_id), values["node_id"])
        self.assertEqual(context.expected_result_version, 0)
        self.assertEqual(context.run_id, "test-run")

    def test_reject_missing_runtime_context_header(self) -> None:
        """缺少节点请求头时不能构造 MCP 运行上下文。"""
        headers, _ = self._build_headers()
        del headers[RUNTIME_CONTEXT_HEADERS["node_id"]]

        with self.assertRaises(BusinessException):
            parse_mcp_runtime_context(headers)

    def test_tool_schema_hides_business_identifiers(self) -> None:
        """模型只能看到结果和摘要，不能填写节点归属字段。"""
        mcp = create_mcp_server()
        tools = asyncio.run(mcp.list_tools())
        tool = next(item for item in tools if item.name == "save_stage_result")
        properties = set((tool.parameters or {}).get("properties", {}))

        self.assertEqual(properties, {"result", "summary"})

    def test_runtime_save_validates_and_updates_node(self) -> None:
        """MCP 保存入口应校验上下文后更新节点结果和版本。"""
        user_id = uuid4()
        project_id = uuid4()
        branch_id = uuid4()
        node_id = uuid4()
        node = SimpleNamespace(
            node_id=node_id,
            project_id=project_id,
            branch_id=branch_id,
            stage_code="project_preparation",
            status="working",
            result_version=0,
            result_data={},
            summary=None,
            result_updated_at=None,
        )
        repository = MagicMock()
        repository.get_owned_node_for_update.return_value = node
        db = MagicMock()
        service = WorkflowService(repository=repository)

        response = service.save_stage_result_from_runtime(
            db,
            user_id=user_id,
            project_id=project_id,
            branch_id=branch_id,
            node_id=node_id,
            stage_code="project_preparation",
            expected_version=0,
            result={"activity_goal": "新品发布"},
            result_summary="项目准备信息已整理",
        )

        self.assertTrue(response.saved)
        self.assertTrue(response.can_advance)
        self.assertEqual(response.result_version, 1)
        self.assertEqual(node.status, "ready")
        db.commit.assert_called_once()

    def test_runtime_save_rejects_mismatched_project(self) -> None:
        """运行上下文项目与节点不一致时必须拒绝写入。"""
        node = SimpleNamespace(
            node_id=uuid4(),
            project_id=uuid4(),
            branch_id=uuid4(),
            stage_code="project_preparation",
        )
        repository = MagicMock()
        repository.get_owned_node_for_update.return_value = node
        service = WorkflowService(repository=repository)

        with self.assertRaises(BusinessException):
            service.save_stage_result_from_runtime(
                MagicMock(),
                user_id=uuid4(),
                project_id=uuid4(),
                branch_id=node.branch_id,
                node_id=node.node_id,
                stage_code=node.stage_code,
                expected_version=0,
                result={"value": 1},
                result_summary=None,
            )


if __name__ == "__main__":
    unittest.main()
