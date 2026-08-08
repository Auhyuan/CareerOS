"""Hai-agent MCP Runtime Context 与工作流工具测试。"""

import asyncio
import base64
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from app.common.core.exceptions import BusinessException
from app.server.mcp.runtime_context import (
    RUNTIME_INPUTS_HEADER,
    RUN_ID_HEADER,
    parse_mcp_runtime_context,
)
from app.server.mcp.server import create_mcp_server
from app.server.workflow.src.service.workflow_service import WorkflowService


class MCPRuntimeContextTests(unittest.TestCase):
    """验证 MCP 工具 Schema、完整 inputs 解析和节点边界。"""

    @staticmethod
    def _build_headers(**overrides) -> tuple[dict[str, str], dict[str, object]]:
        """创建包含完整 inputs 的测试请求头。"""
        values: dict[str, object] = {
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "branch_id": str(uuid4()),
            "node_id": str(uuid4()),
            "stage_code": "project_preparation",
            "project_context": {"name": "新品发布会", "tags": ["科技", "深圳"]},
        }
        values.update(overrides)
        payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {
            RUNTIME_INPUTS_HEADER: base64.urlsafe_b64encode(payload).decode("ascii"),
            RUN_ID_HEADER: "test-run",
        }
        return headers, values

    def test_parse_complete_runtime_inputs(self) -> None:
        """统一请求头应完整还原顶层字段、嵌套对象和数组。"""
        headers, values = self._build_headers()
        context = parse_mcp_runtime_context(headers)

        self.assertEqual(context.inputs, values)
        self.assertEqual(context.require_uuid("user_id"), UUID(str(values["user_id"])))
        self.assertEqual(context.require_str("stage_code"), "project_preparation")
        self.assertEqual(context.inputs["project_context"]["tags"], ["科技", "深圳"])
        self.assertEqual(context.run_id, "test-run")

    def test_reject_missing_complete_runtime_inputs_header(self) -> None:
        """缺少统一 inputs 请求头时不能构造 MCP 运行上下文。"""
        with self.assertRaises(BusinessException):
            parse_mcp_runtime_context({RUN_ID_HEADER: "test-run"})

    def test_runtime_context_requires_fields_at_tool_side(self) -> None:
        """具体 MCP 工具应在使用时自行校验所需字段。"""
        headers, _ = self._build_headers()
        context = parse_mcp_runtime_context(headers)

        with self.assertRaisesRegex(BusinessException, "missing_field"):
            context.require("missing_field")

    def test_tool_schema_hides_business_identifiers(self) -> None:
        """模型只能看到结果和摘要，完整 inputs 不进入工具公开 Schema。"""
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
            result={"activity_goal": "新品发布"},
            result_summary="项目准备信息已整理",
        )

        self.assertTrue(response.saved)
        self.assertTrue(response.can_advance)
        self.assertEqual(response.result_version, 1)
        self.assertEqual(node.status, "ready")
        db.commit.assert_called_once()

    def test_runtime_save_allows_multiple_updates_on_same_node(self) -> None:
        """Agent 可在同一分支节点多次保存，最后一次完整结果覆盖前一次。"""
        node = SimpleNamespace(
            node_id=uuid4(),
            project_id=uuid4(),
            branch_id=uuid4(),
            stage_code="project_preparation",
            status="ready",
            result_version=1,
            result_data={"activity_goal": "新品发布"},
            summary="第一版准备结果",
            result_updated_at=None,
        )
        repository = MagicMock()
        repository.get_owned_node_for_update.return_value = node
        db = MagicMock()
        service = WorkflowService(repository=repository)

        response = service.save_stage_result_from_runtime(
            db,
            user_id=uuid4(),
            project_id=node.project_id,
            branch_id=node.branch_id,
            node_id=node.node_id,
            stage_code=node.stage_code,
            result={"activity_goal": "新品发布", "budget": "50 万元"},
            result_summary="补充预算后的准备结果",
        )

        self.assertEqual(response.result_version, 2)
        self.assertEqual(node.result_data["budget"], "50 万元")
        self.assertEqual(node.summary, "补充预算后的准备结果")
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
                result={"value": 1},
                result_summary=None,
            )


if __name__ == "__main__":
    unittest.main()
