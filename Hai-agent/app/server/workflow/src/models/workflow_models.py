from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db.postgres import Base


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class WorkflowBranchModel(Base):
    """保存项目中的一条方案演进分支。"""

    __tablename__ = "workflow_branches"
    __table_args__ = {"schema": "hai_agent"}

    branch_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("hai_agent.projects.project_id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_branch_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("hai_agent.workflow_branches.branch_id", ondelete="SET NULL"), nullable=True
    )
    source_node_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    # head_node_id 的数据库外键由迁移补充，避免与 workflow_nodes 形成 ORM 表级循环依赖。
    head_node_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowNodeModel(Base):
    """保存分支中的阶段执行节点，节点只记录父节点关系。"""

    __tablename__ = "workflow_nodes"
    __table_args__ = (
        UniqueConstraint("branch_id", "sequence_no", name="uq_workflow_nodes_branch_sequence"),
        {"schema": "hai_agent"},
    )

    node_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("hai_agent.projects.project_id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("hai_agent.workflow_branches.branch_id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_node_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("hai_agent.workflow_nodes.node_id", ondelete="RESTRICT"), nullable=True, index=True
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    node_type: Mapped[str] = mapped_column(String(60), nullable=False, default="stage")
    stage_code: Mapped[str] = mapped_column("stage", String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="working")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    handoff_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agent_thread_id: Mapped[str | None] = mapped_column(String(150), nullable=True, unique=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
