from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.common.core.exceptions import BusinessException
from app.server.project.src.models.project_model import ProjectModel
from app.server.project.src.repository.project_repository import ProjectRepository
from app.server.project.src.schemas.project_schemas import (
    BranchResponse,
    NodeResponse,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectSearchRequest,
)
from app.server.workflow.src.config.stage_config import get_stage_definition
from app.server.workflow.src.models.workflow_models import WorkflowBranchModel, WorkflowNodeModel


class ProjectService:
    """实现用户项目创建、列表和详情查询。"""

    def __init__(self, repository: ProjectRepository | None = None):
        """初始化项目服务及其数据仓储。"""
        self.repository = repository or ProjectRepository()

    def create_project(self, db: Session, user_id: UUID, request: ProjectCreateRequest) -> ProjectDetailResponse:
        """创建项目、主分支和项目准备根节点。"""
        project_id = uuid4()
        branch_id = uuid4()
        node_id = uuid4()
        agent_thread_id = self._build_thread_id(project_id, node_id)
        initial_stage = get_stage_definition("project_preparation")

        project = ProjectModel(
            project_id=project_id,
            user_id=user_id,
            name=request.name.strip(),
            customer_name=request.customer_name,
            brand_name=request.brand_name,
            event_type=request.event_type,
            description=request.description,
            current_branch_id=branch_id,
            current_node_id=node_id,
            metadata_json=request.metadata,
        )
        branch = WorkflowBranchModel(
            branch_id=branch_id,
            project_id=project_id,
            name="main",
            head_node_id=node_id,
            is_main=True,
        )
        node = WorkflowNodeModel(
            node_id=node_id,
            project_id=project_id,
            branch_id=branch_id,
            parent_node_id=None,
            sequence_no=1,
            stage_code=initial_stage.stage_code,
            title=initial_stage.title,
            agent_id=initial_stage.agent_id,
            agent_thread_id=agent_thread_id,
        )
        self.repository.add_project_graph(db, project, branch, node)
        db.commit()
        return self._build_detail(project, [branch], [node])

    def search_projects(
        self, db: Session, user_id: UUID, request: ProjectSearchRequest
    ) -> ProjectListResponse:
        """分页查询当前登录用户自己的项目。"""
        projects, total = self.repository.search_owned_projects(
            db, user_id, request.keyword, request.status, request.page, request.page_size
        )
        return ProjectListResponse(
            items=[self._project_response(project) for project in projects],
            total=total,
            page=request.page,
            page_size=request.page_size,
        )

    def get_project_detail(self, db: Session, user_id: UUID, project_id: UUID) -> ProjectDetailResponse:
        """查询当前用户项目及其分支、节点树数据。"""
        project = self.repository.get_owned_project(db, user_id, project_id)
        if project is None:
            raise BusinessException(404, "项目不存在")
        branches = self.repository.list_project_branches(db, project_id)
        nodes = self.repository.list_project_nodes(db, project_id)
        return self._build_detail(project, branches, nodes)

    @staticmethod
    def _build_thread_id(project_id: UUID, node_id: UUID) -> str:
        """为步骤节点创建独立且不可复用的 LangGraph thread_id。"""
        return f"hai:{project_id}:{node_id}:{uuid4().hex}"

    @staticmethod
    def _project_response(project: ProjectModel) -> ProjectResponse:
        """把项目 ORM 对象转换为接口响应。"""
        return ProjectResponse(
            project_id=project.project_id,
            name=project.name,
            customer_name=project.customer_name,
            brand_name=project.brand_name,
            event_type=project.event_type,
            description=project.description,
            status=project.status,
            current_stage=project.current_stage,
            current_branch_id=project.current_branch_id,
            current_node_id=project.current_node_id,
            metadata=project.metadata_json,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def _build_detail(
        self, project: ProjectModel, branches: list[WorkflowBranchModel], nodes: list[WorkflowNodeModel]
    ) -> ProjectDetailResponse:
        """组合项目、分支和节点响应。"""
        return ProjectDetailResponse(
            project=self._project_response(project),
            branches=[
                BranchResponse(
                    branch_id=item.branch_id,
                    name=item.name,
                    source_branch_id=item.source_branch_id,
                    source_node_id=item.source_node_id,
                    head_node_id=item.head_node_id,
                    status=item.status,
                    is_main=item.is_main,
                    created_at=item.created_at,
                )
                for item in branches
            ],
            nodes=[
                NodeResponse(
                    node_id=item.node_id,
                    branch_id=item.branch_id,
                    parent_node_id=item.parent_node_id,
                    sequence_no=item.sequence_no,
                    stage_code=item.stage_code,
                    status=item.status,
                    title=item.title,
                    summary=item.summary,
                    input_context=item.input_context,
                    result_data=item.result_data,
                    handoff_context=item.handoff_context,
                    result_version=item.result_version,
                    agent_id=item.agent_id,
                    agent_thread_id=item.agent_thread_id,
                    created_at=item.created_at,
                    completed_at=item.completed_at,
                )
                for item in nodes
            ],
        )
