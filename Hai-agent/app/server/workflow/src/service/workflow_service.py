from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.common.core.exceptions import BusinessException
from app.server.project.src.schemas.project_schemas import BranchResponse, NodeResponse
from app.server.workflow.src.config.stage_config import get_next_stage_definition, get_stage_definition
from app.server.workflow.src.models.workflow_models import WorkflowBranchModel, WorkflowNodeModel
from app.server.workflow.src.repository.workflow_repository import WorkflowRepository
from app.server.workflow.src.schemas.workflow_schemas import (
    BranchCreateRequest,
    BranchCreateResponse,
    NodeAdvanceRequest,
    NodeAdvanceResponse,
    StageResultSaveRequest,
    StageResultSaveResponse,
)


class WorkflowService:
    """实现通用阶段结果保存和用户确认后的节点推进。"""

    def __init__(self, repository: WorkflowRepository | None = None):
        """初始化工作流服务及其数据仓储。"""
        self.repository = repository or WorkflowRepository()

    def save_stage_result(
        self, db: Session, user_id: UUID, request: StageResultSaveRequest
    ) -> StageResultSaveResponse:
        """以乐观锁方式更新当前节点的 JSON 阶段结果。"""
        node = self.repository.get_owned_node_for_update(db, user_id, request.node_id)
        if node is None:
            raise BusinessException(404, "节点不存在")
        return self._save_locked_stage_result(
            db,
            node,
            result=request.result,
            result_summary=request.result_summary,
            expected_version=request.expected_version,
        )

    def save_stage_result_from_runtime(
        self,
        db: Session,
        *,
        user_id: UUID,
        project_id: UUID,
        branch_id: UUID,
        node_id: UUID,
        stage_code: str,
        expected_version: int,
        result: dict,
        result_summary: str | None,
    ) -> StageResultSaveResponse:
        """使用系统运行上下文保存阶段结果，并校验完整节点归属。

        该入口供 MCP 工具使用。业务标识由 AI-backend 从 Runtime Context
        注入，模型只负责生成 result 和 result_summary。
        """
        node = self.repository.get_owned_node_for_update(db, user_id, node_id)
        if node is None:
            raise BusinessException(404, "节点不存在")
        if node.project_id != project_id:
            raise BusinessException(409, "运行上下文中的项目与节点不匹配")
        if node.branch_id != branch_id:
            raise BusinessException(409, "运行上下文中的分支与节点不匹配")
        if node.stage_code != stage_code:
            raise BusinessException(409, "运行上下文中的阶段与节点不匹配")
        return self._save_locked_stage_result(
            db,
            node,
            result=result,
            result_summary=result_summary,
            expected_version=expected_version,
        )

    @staticmethod
    def _save_locked_stage_result(
        db: Session,
        node: WorkflowNodeModel,
        *,
        result: dict,
        result_summary: str | None,
        expected_version: int,
    ) -> StageResultSaveResponse:
        """更新已加行锁的节点结果，并执行状态和版本校验。"""
        if node.status in {"completed", "cancelled"}:
            raise BusinessException(409, "已完成或已取消的节点不能更新结果")
        if node.result_version != expected_version:
            raise BusinessException(409, f"节点结果已更新，当前版本为 {node.result_version}")

        # 第一版先执行通用非空校验；后续由阶段配置的 output_schema 扩展细粒度校验。
        can_advance = bool(result)
        node.result_data = deepcopy(result)
        node.summary = result_summary
        node.result_version += 1
        node.result_updated_at = datetime.now(timezone.utc)
        node.status = "ready" if can_advance else "working"
        db.commit()
        return StageResultSaveResponse(
            saved=True,
            node_id=node.node_id,
            result_version=node.result_version,
            node_status=node.status,
            can_advance=can_advance,
        )

    def create_branch_from_node(
        self,
        db: Session,
        user_id: UUID,
        request: BranchCreateRequest,
    ) -> BranchCreateResponse:
        """从历史节点复制业务基线，创建独立分支和全新 Agent 会话节点。"""
        source_node = self.repository.get_owned_node_for_update(db, user_id, request.source_node_id)
        if source_node is None:
            raise BusinessException(404, "来源节点不存在")
        if source_node.status not in {"ready", "completed"}:
            raise BusinessException(409, "只有已保存稳定结果的节点才能创建新分支")
        if not source_node.result_data or source_node.result_version < 1:
            raise BusinessException(409, "来源节点尚未保存阶段结果，不能创建新分支")
        if source_node.result_version != request.expected_result_version:
            raise BusinessException(409, f"节点结果版本已变化，当前版本为 {source_node.result_version}")

        source_branch = self.repository.get_branch_for_update(db, source_node.branch_id)
        project = self.repository.get_project_for_update(db, source_node.project_id, user_id)
        if source_branch is None or project is None:
            raise BusinessException(404, "项目或来源分支不存在")
        if source_branch.project_id != source_node.project_id:
            raise BusinessException(409, "来源分支与节点所属项目不匹配")
        if project.status != "active":
            raise BusinessException(409, "非活动项目不能创建新分支")

        # 新分支从来源节点处产生树状分叉。新节点保留该阶段的业务结果作为修改基线，
        # 但不复制旧 Checkpoint、运行状态和版本号，避免新旧分支的 Agent 上下文互相污染。
        stage = get_stage_definition(source_node.stage_code)
        branch_id = uuid4()
        node_id = uuid4()
        branch = WorkflowBranchModel(
            branch_id=branch_id,
            project_id=source_node.project_id,
            name=request.branch_name,
            source_branch_id=source_branch.branch_id,
            source_node_id=source_node.node_id,
            status="active",
            is_main=False,
        )
        node = WorkflowNodeModel(
            node_id=node_id,
            project_id=source_node.project_id,
            branch_id=branch_id,
            parent_node_id=source_node.node_id,
            sequence_no=source_node.sequence_no,
            stage_code=source_node.stage_code,
            status="working",
            title=stage.title,
            summary=source_node.summary,
            input_context=deepcopy(source_node.input_context),
            result_data=deepcopy(source_node.result_data),
            handoff_context={},
            result_version=0,
            agent_id=stage.agent_id,
            agent_thread_id=self._build_thread_id(source_node.project_id, node_id),
        )
        self.repository.add_branch_with_node(db, branch, node)
        branch.head_node_id = node.node_id
        project.current_branch_id = branch.branch_id
        project.current_node_id = node.node_id
        project.current_stage = node.stage_code
        db.commit()

        return BranchCreateResponse(
            branch=self._branch_response(branch),
            node=self._node_response(node),
        )

    def advance_node(self, db: Session, user_id: UUID, request: NodeAdvanceRequest) -> NodeAdvanceResponse:
        """冻结 ready 节点，并创建使用全新 Checkpoint 的下一步骤节点。"""
        node = self.repository.get_owned_node_for_update(db, user_id, request.node_id)
        if node is None:
            raise BusinessException(404, "节点不存在")

        # 重复点击时直接返回同一分支中已经创建的子节点，保证推进接口幂等。
        existing_child = self.repository.get_child_in_branch(db, node.branch_id, node.node_id)
        if node.status == "completed" and existing_child is not None:
            return NodeAdvanceResponse(
                current_node_id=node.node_id,
                next_node=self._node_response(existing_child),
                reused_existing_node=True,
            )
        if node.status != "ready":
            raise BusinessException(409, "当前节点尚未准备好，不能进入下一步")
        if node.result_version != request.expected_result_version:
            raise BusinessException(409, f"节点结果版本已变化，当前版本为 {node.result_version}")

        branch = self.repository.get_branch_for_update(db, node.branch_id)
        project = self.repository.get_project_for_update(db, node.project_id, user_id)
        if branch is None or project is None:
            raise BusinessException(404, "项目或分支不存在")
        if branch.head_node_id != node.node_id:
            raise BusinessException(409, "历史节点不能直接推进，请先从该节点创建新分支")

        next_stage = get_next_stage_definition(node.stage_code)
        now = datetime.now(timezone.utc)
        node.status = "completed"
        node.completed_at = now
        node.handoff_context = self._build_handoff_context(node)

        next_node_id = uuid4()
        next_node = WorkflowNodeModel(
            node_id=next_node_id,
            project_id=node.project_id,
            branch_id=node.branch_id,
            parent_node_id=node.node_id,
            sequence_no=node.sequence_no + 1,
            stage_code=next_stage.stage_code,
            title=next_stage.title,
            input_context=deepcopy(node.handoff_context),
            agent_id=next_stage.agent_id,
            agent_thread_id=self._build_thread_id(node.project_id, next_node_id),
            status="working",
        )
        self.repository.add_node(db, next_node)
        branch.head_node_id = next_node.node_id
        project.current_branch_id = branch.branch_id
        project.current_node_id = next_node.node_id
        project.current_stage = next_node.stage_code
        db.commit()
        return NodeAdvanceResponse(
            current_node_id=node.node_id,
            next_node=self._node_response(next_node),
        )

    @staticmethod
    def _build_handoff_context(node: WorkflowNodeModel) -> dict:
        """把输入上下文和当前阶段结果合并成下游可消费的累计业务状态。"""
        context = deepcopy(node.input_context)
        stage_results = dict(context.get("stage_results") or {})
        stage_results[node.stage_code] = deepcopy(node.result_data)
        context.update(
            {
                "project_id": str(node.project_id),
                "source_node_id": str(node.node_id),
                "completed_stage": node.stage_code,
                "stage_results": stage_results,
                "result_summary": node.summary,
            }
        )
        return context

    @staticmethod
    def _build_thread_id(project_id: UUID, node_id: UUID) -> str:
        """为下一步骤节点生成新的 LangGraph thread_id。"""
        return f"hai:{project_id}:{node_id}:{uuid4().hex}"

    @staticmethod
    def _branch_response(branch: WorkflowBranchModel) -> BranchResponse:
        """把分支 ORM 对象转换为接口响应。"""
        return BranchResponse(
            branch_id=branch.branch_id,
            name=branch.name,
            source_branch_id=branch.source_branch_id,
            source_node_id=branch.source_node_id,
            head_node_id=branch.head_node_id,
            status=branch.status,
            is_main=branch.is_main,
            created_at=branch.created_at,
        )

    @staticmethod
    def _node_response(node: WorkflowNodeModel) -> NodeResponse:
        """把节点 ORM 对象转换为接口响应。"""
        return NodeResponse(
            node_id=node.node_id,
            branch_id=node.branch_id,
            parent_node_id=node.parent_node_id,
            sequence_no=node.sequence_no,
            stage_code=node.stage_code,
            status=node.status,
            title=node.title,
            summary=node.summary,
            input_context=node.input_context,
            result_data=node.result_data,
            handoff_context=node.handoff_context,
            result_version=node.result_version,
            agent_id=node.agent_id,
            agent_thread_id=node.agent_thread_id,
            created_at=node.created_at,
            completed_at=node.completed_at,
        )
