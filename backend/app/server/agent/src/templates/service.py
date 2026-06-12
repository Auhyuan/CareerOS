from sqlmodel import Session

from app.server.agent.src.templates.models import AgentTemplate
from app.server.agent.src.templates.repository import AgentTemplateRepository
from app.server.agent.src.templates.schemas import (
    AgentTemplateSearchRequest,
    AgentTemplateSearchResponse,
    AgentTemplateUpsertRequest,
    AgentTemplateView,
)


class AgentTemplateService:
    """Agent 模板服务，负责模板的创建、更新和查询。"""

    def __init__(self, repository: AgentTemplateRepository | None = None):
        """
        初始化 Agent 模板服务。

        Args:
            repository: Agent 模板数据访问层，默认使用 PostgreSQL 实现。
        """
        self.repository = repository or AgentTemplateRepository()

    def upsert_template(self, db: Session, request: AgentTemplateUpsertRequest) -> AgentTemplateView:
        """
        创建或更新 Agent 模板。

        Args:
            db: 数据库会话。
            request: 模板创建或更新参数。

        Returns:
            模板视图。
        """
        template = self.repository.upsert(
            db,
            agent_id=request.agent_id,
            agent_name=request.agent_name,
            description=request.description,
            config=request.config,
            status=request.status,
        )
        return self.to_view(template)

    def get_template(self, db: Session, agent_id: str) -> AgentTemplateView | None:
        """
        根据 agent_id 查询 Agent 模板详情。

        Args:
            db: 数据库会话。
            agent_id: Agent 稳定业务 ID。

        Returns:
            模板视图；不存在时返回 None。
        """
        template = self.repository.get_by_agent_id(db, agent_id)
        if template is None:
            return None
        return self.to_view(template)

    def search_templates(self, db: Session, request: AgentTemplateSearchRequest) -> AgentTemplateSearchResponse:
        """
        分页查询 Agent 模板列表。

        Args:
            db: 数据库会话。
            request: 模板查询参数。

        Returns:
            模板分页查询结果。
        """
        rows, total = self.repository.list_templates(
            db,
            keyword=request.keyword,
            status=request.status,
            page=request.page,
            page_size=request.page_size,
        )
        return AgentTemplateSearchResponse(
            total=total,
            page=request.page,
            page_size=request.page_size,
            items=[self.to_view(row) for row in rows],
        )

    def to_view(self, template: AgentTemplate) -> AgentTemplateView:
        """
        将数据库模型转换为接口响应视图。

        Args:
            template: Agent 模板数据库模型。

        Returns:
            Agent 模板接口响应视图。
        """
        return AgentTemplateView(
            agent_id=template.agent_id,
            agent_name=template.agent_name,
            description=template.description,
            config=template.config,
            status=template.status,
            created_at=template.created_at.isoformat() if template.created_at else None,
            updated_at=template.updated_at.isoformat() if template.updated_at else None,
        )
