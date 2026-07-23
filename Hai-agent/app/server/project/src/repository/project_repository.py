from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.server.project.src.models.project_model import ProjectModel
from app.server.workflow.src.models.workflow_models import WorkflowBranchModel, WorkflowNodeModel


class ProjectRepository:
    """封装按 user_id 隔离的项目、分支和节点查询。"""

    @staticmethod
    def add_project_graph(
        db: Session, project: ProjectModel, branch: WorkflowBranchModel, node: WorkflowNodeModel
    ) -> None:
        """在同一事务中加入项目、主分支和根节点。"""
        db.add_all([project, branch, node])

    @staticmethod
    def get_owned_project(db: Session, user_id: UUID, project_id: UUID) -> ProjectModel | None:
        """根据用户和项目 ID 查询归属于当前用户的项目。"""
        return db.scalar(
            select(ProjectModel).where(
                ProjectModel.project_id == project_id,
                ProjectModel.user_id == user_id,
            )
        )

    @staticmethod
    def search_owned_projects(
        db: Session, user_id: UUID, keyword: str | None, status: str | None, page: int, page_size: int
    ) -> tuple[list[ProjectModel], int]:
        """分页查询当前用户项目，并返回结果和总数。"""
        filters = [ProjectModel.user_id == user_id]
        if status:
            filters.append(ProjectModel.status == status)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            filters.append(
                or_(
                    ProjectModel.name.ilike(pattern),
                    ProjectModel.customer_name.ilike(pattern),
                    ProjectModel.brand_name.ilike(pattern),
                )
            )

        total = db.scalar(select(func.count()).select_from(ProjectModel).where(*filters)) or 0
        statement = (
            select(ProjectModel)
            .where(*filters)
            .order_by(ProjectModel.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(db.scalars(statement).all()), int(total)

    @staticmethod
    def list_project_branches(db: Session, project_id: UUID) -> list[WorkflowBranchModel]:
        """查询项目的全部未归档分支。"""
        statement = (
            select(WorkflowBranchModel)
            .where(
                WorkflowBranchModel.project_id == project_id,
                WorkflowBranchModel.status != "archived",
            )
            .order_by(WorkflowBranchModel.created_at.asc())
        )
        return list(db.scalars(statement).all())

    @staticmethod
    def list_project_nodes(db: Session, project_id: UUID) -> list[WorkflowNodeModel]:
        """查询项目全部节点，按分支和分支内序号稳定排序。"""
        statement = (
            select(WorkflowNodeModel)
            .where(WorkflowNodeModel.project_id == project_id)
            .order_by(WorkflowNodeModel.branch_id.asc(), WorkflowNodeModel.sequence_no.asc())
        )
        return list(db.scalars(statement).all())
