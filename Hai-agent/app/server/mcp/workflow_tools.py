"""向 FastMCP 注册 Hai-agent 工作流业务工具。"""

from typing import Any

from fastmcp import FastMCP

from app.common.db.postgres import session_scope
from app.server.mcp.runtime_context import get_mcp_runtime_context
from app.server.workflow.src.service.workflow_service import WorkflowService


def register_workflow_tools(mcp: FastMCP) -> None:
    """注册工作流节点结果保存工具。"""
    workflow_service = WorkflowService()

    @mcp.tool(
        name="save_stage_result",
        description=(
            "保存当前工作流节点的阶段结果。"
            "project_id、branch_id、node_id、stage_code、用户归属和结果版本由系统运行上下文自动注入，"
            "不要在参数中填写。result 必须是当前阶段可供下一阶段消费的完整 JSON 对象。"
        ),
    )
    def save_stage_result(result: dict[str, Any], summary: str | None = None) -> dict[str, Any]:
        """保存 Agent 生成的当前阶段结构化结果。

        Args:
            result: 当前阶段完整结构化结果。
            summary: 面向用户和后续阶段的简短结果摘要。

        Returns:
            保存状态、最新版本以及当前节点是否允许推进。
        """
        runtime_context = get_mcp_runtime_context()
        with session_scope() as db:
            response = workflow_service.save_stage_result_from_runtime(
                db,
                user_id=runtime_context.user_id,
                project_id=runtime_context.project_id,
                branch_id=runtime_context.branch_id,
                node_id=runtime_context.node_id,
                stage_code=runtime_context.stage_code,
                expected_version=runtime_context.expected_result_version,
                result=result,
                result_summary=summary,
            )
        return response.model_dump(mode="json")
