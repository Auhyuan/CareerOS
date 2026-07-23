from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.server.project.src.models.project_model import ProjectModel
from app.server.workflow.src.models.workflow_models import WorkflowBranchModel, WorkflowNodeModel


class WorkflowRepository:
    """封装经过项目归属校验的节点和分支数据库操作。"""

    @staticmethod
    def get_owned_node_context(
        db: Session,
        user_id: UUID,
        node_id: UUID,
    ) -> tuple[WorkflowNodeModel, ProjectModel] | None:
        """查询当前用户拥有的节点及项目，不在 Agent 执行期间持有行锁。"""
        statement = (
            select(WorkflowNodeModel, ProjectModel)
            .join(ProjectModel, ProjectModel.project_id == WorkflowNodeModel.project_id)
            .where(
                WorkflowNodeModel.node_id == node_id,
                ProjectModel.user_id == user_id,
            )
        )
        row = db.execute(statement).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    @staticmethod
    def get_owned_node_for_update(db: Session, user_id: UUID, node_id: UUID) -> WorkflowNodeModel | None:
        """锁定当前用户拥有的节点，防止并发保存或推进。"""
        statement = (
            select(WorkflowNodeModel)
            .join(ProjectModel, ProjectModel.project_id == WorkflowNodeModel.project_id)
            .where(WorkflowNodeModel.node_id == node_id, ProjectModel.user_id == user_id)
            .with_for_update()
        )
        return db.scalar(statement)

    @staticmethod
    def get_branch_for_update(db: Session, branch_id: UUID) -> WorkflowBranchModel | None:
        """锁定节点所属分支。"""
        return db.scalar(
            select(WorkflowBranchModel)
            .where(WorkflowBranchModel.branch_id == branch_id)
            .with_for_update()
        )

    @staticmethod
    def get_project_for_update(db: Session, project_id: UUID, user_id: UUID) -> ProjectModel | None:
        """锁定当前用户拥有的项目聚合根。"""
        return db.scalar(
            select(ProjectModel)
            .where(ProjectModel.project_id == project_id, ProjectModel.user_id == user_id)
            .with_for_update()
        )

    @staticmethod
    def get_child_in_branch(
        db: Session, branch_id: UUID, parent_node_id: UUID
    ) -> WorkflowNodeModel | None:
        """查询同一分支中已由当前节点创建的直接子节点。"""
        return db.scalar(
            select(WorkflowNodeModel).where(
                WorkflowNodeModel.branch_id == branch_id,
                WorkflowNodeModel.parent_node_id == parent_node_id,
            )
        )

    @staticmethod
    def add_branch_with_node(
        db: Session,
        branch: WorkflowBranchModel,
        node: WorkflowNodeModel,
    ) -> None:
        """按外键依赖顺序新增分支及其首个节点。"""
        # 先落入分支主记录，再创建引用该分支的节点，避免 flush 时违反外键约束。
        db.add(branch)
        db.flush()
        db.add(node)
        db.flush()

    @staticmethod
    def add_node(db: Session, node: WorkflowNodeModel) -> None:
        """把新步骤节点加入当前事务。"""
        db.add(node)
        db.flush()
