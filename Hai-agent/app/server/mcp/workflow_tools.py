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
            "保存当前工作流节点已经完成并经用户确认的最终阶段结果。"
            "资料仍在收集、用户只补充单条信息或尚未确认最终结论时，不得调用本工具。"
            "完整 inputs 由系统通过 Runtime Context 自动传入，项目、分支、节点、阶段和用户归属无需填写。"
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
                user_id=runtime_context.require_uuid("user_id"),
                project_id=runtime_context.require_uuid("project_id"),
                branch_id=runtime_context.require_uuid("branch_id"),
                node_id=runtime_context.require_uuid("node_id"),
                stage_code=runtime_context.require_str("stage_code"),
                result=result,
                result_summary=summary,
            )
        return response.model_dump(mode="json")
