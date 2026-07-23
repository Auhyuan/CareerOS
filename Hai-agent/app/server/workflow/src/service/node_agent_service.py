"""组装当前工作流节点的 Agent 调用参数。"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.common.core.exceptions import BusinessException
from app.server.project.src.models.project_model import ProjectModel
from app.server.workflow.src.models.workflow_models import WorkflowNodeModel
from app.server.workflow.src.repository.workflow_repository import WorkflowRepository
from app.server.workflow.src.schemas.workflow_schemas import NodeAgentMessageRequest


@dataclass(frozen=True)
class PreparedNodeAgentMessage:
    """保存已经过归属校验的 AI-backend Agent 调用信息。"""

    node_id: UUID
    agent_id: str
    conversation_id: str
    payload: dict[str, Any]


class NodeAgentService:
    """校验节点归属并组装阶段 Agent 所需的动态上下文。"""

    def __init__(self, repository: WorkflowRepository | None = None):
        """初始化节点 Agent 服务及其数据仓储。"""
        self.repository = repository or WorkflowRepository()

    def prepare_message(
        self,
        db: Session,
        user_id: UUID,
        request: NodeAgentMessageRequest,
    ) -> PreparedNodeAgentMessage:
        """读取当前节点和项目，构造 AI-backend `/agent/messages` 请求。"""
        owned_context = self.repository.get_owned_node_context(db, user_id, request.node_id)
        if owned_context is None:
            raise BusinessException(404, "节点不存在")
        node, project = owned_context
        self._validate_node(node, project)

        inputs = self._build_runtime_inputs(user_id, project, node)
        payload: dict[str, Any] = {
            "agent_id": node.agent_id,
            "conversation_id": node.agent_thread_id,
            "message": request.message,
            "message_type": request.message_type,
            "payload": deepcopy(request.payload),
            "stream": request.stream,
            "inputs": inputs,
            "file_ids": list(request.file_ids),
        }
        if request.knowledge_base_ids:
            payload["knowledge"] = {
                "knowledge_base_ids": [str(item) for item in request.knowledge_base_ids]
            }

        return PreparedNodeAgentMessage(
            node_id=node.node_id,
            agent_id=str(node.agent_id),
            conversation_id=str(node.agent_thread_id),
            payload=payload,
        )

    @staticmethod
    def _validate_node(node: WorkflowNodeModel, project: ProjectModel) -> None:
        """检查项目和节点当前是否允许继续与 Agent 交互。"""
        if project.status != "active":
            raise BusinessException(409, "当前项目不可继续执行")
        if node.status in {"completed", "cancelled"}:
            raise BusinessException(409, "已完成或已取消的节点不能继续对话")
        if not node.agent_id:
            raise BusinessException(409, "当前阶段尚未配置 Agent 模板")
        if not node.agent_thread_id:
            raise BusinessException(409, "当前节点缺少 Agent 会话标识")

    @classmethod
    def _build_runtime_inputs(
        cls,
        user_id: UUID,
        project: ProjectModel,
        node: WorkflowNodeModel,
    ) -> dict[str, Any]:
        """构造提示词渲染和 MCP 自动注入共同使用的 inputs。"""
        input_context = deepcopy(node.input_context or {})
        stage_results = deepcopy(input_context.get("stage_results") or {})
        previous_stage_code = str(input_context.get("completed_stage") or "").strip()
        previous_stage_result = (
            deepcopy(stage_results.get(previous_stage_code) or {})
            if previous_stage_code
            else {}
        )

        project_context = {
            "project_id": str(project.project_id),
            "project_name": project.name,
            "customer_name": project.customer_name,
            "brand_name": project.brand_name,
            "event_type": project.event_type,
            "description": project.description,
            "metadata": deepcopy(project.metadata_json or {}),
            "current_stage": node.stage_code,
            "stage_results": stage_results,
        }

        # 这些白名单字段同时供 PromptService 和 MCP ToolCallInterceptor 使用。
        return {
            "user_id": str(user_id),
            "project_id": str(node.project_id),
            "branch_id": str(node.branch_id),
            "node_id": str(node.node_id),
            "stage_code": node.stage_code,
            "expected_result_version": node.result_version,
            "project_context": project_context,
            "previous_stage_result": previous_stage_result,
            "current_stage_result": deepcopy(node.result_data or {}),
        }
