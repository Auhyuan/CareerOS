from sqlmodel import Session

from app.server.agent.src.model import ModelConfigService
from app.server.agent.src.templates.models import AgentTemplate
from app.server.agent.src.templates.repository import AgentTemplateRepository
from app.server.agent.src.templates.schemas import (
    AgentTemplateDeleteRequest,
    AgentTemplateSearchRequest,
    AgentTemplateSearchResponse,
    AgentTemplateUpsertRequest,
    AgentTemplateView,
)


class AgentTemplateService:
    """Agent 模板服务，负责模板的创建、更新、查询和删除。"""

    def __init__(
        self,
        repository: AgentTemplateRepository | None = None,
        model_config_service: ModelConfigService | None = None,
    ):
        """初始化 Agent 模板服务。"""
        self.repository = repository or AgentTemplateRepository()
        self.model_config_service = model_config_service or ModelConfigService()

    def upsert_template(self, db: Session, request: AgentTemplateUpsertRequest) -> AgentTemplateView:
        """创建或更新 Agent 模板，并校验模板绑定的 chat 模型。"""
        model_code = request.config.runtime_options.model_code
        # Agent 模板必须显式绑定一个已启用的 chat 模型，避免误用所谓默认模型。
        self.model_config_service.require_enabled_chat_model(db, model_code)

        template = self.repository.upsert(
            db,
            agent_id=request.agent_id,
            agent_name=request.agent_name,
            description=request.description,
            config=self._clean_template_config(request.config.model_dump(mode="json")),
            status=request.status,
        )
        return self.to_view(template)

    def _clean_template_config(self, config: dict) -> dict:
        """Remove deprecated runtime-only fields before template config is stored or returned."""
        cleaned_config = dict(config or {})
        # Remove the deprecated structured-output schema key from older template records.
        deprecated_schema_key = "response_" + "format"
        cleaned_config.pop(deprecated_schema_key, None)
        return cleaned_config

    def get_template(self, db: Session, agent_id: str) -> AgentTemplateView | None:
        """根据 agent_id 查询 Agent 模板详情。"""
        template = self.repository.get_by_agent_id(db, agent_id)
        if template is None:
            return None
        return self.to_view(template)

    def search_templates(self, db: Session, request: AgentTemplateSearchRequest) -> AgentTemplateSearchResponse:
        """分页查询 Agent 模板列表。"""
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

    def delete_templates(self, db: Session, request: AgentTemplateDeleteRequest) -> int:
        """批量删除 Agent 模板。"""
        return self.repository.delete_by_agent_ids(db, request.agent_ids)

    def to_view(self, template: AgentTemplate) -> AgentTemplateView:
        """将数据库模型转换为接口响应视图。"""
        return AgentTemplateView(
            agent_id=template.agent_id,
            agent_name=template.agent_name,
            description=template.description,
            config=self._clean_template_config(template.config),
            status=template.status,
            created_at=template.created_at.isoformat() if template.created_at else None,
            updated_at=template.updated_at.isoformat() if template.updated_at else None,
        )
