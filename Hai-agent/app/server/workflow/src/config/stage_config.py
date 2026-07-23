from dataclasses import dataclass

from app.common.config.settings import get_settings
from app.common.core.exceptions import BusinessException


@dataclass(frozen=True)
class StageDefinition:
    """定义一个工作流阶段及其固定后继阶段。"""

    stage_code: str
    title: str
    agent_id: str | None
    next_stage_code: str | None


def get_stage_definitions() -> dict[str, StageDefinition]:
    """根据系统配置构建活动策划阶段注册表。"""
    settings = get_settings()
    return {
        "project_preparation": StageDefinition(
            stage_code="project_preparation",
            title="项目准备",
            agent_id=settings.project_preparation_agent_id,
            next_stage_code="requirement_confirmation",
        ),
        "requirement_confirmation": StageDefinition(
            stage_code="requirement_confirmation",
            title="需求确认",
            agent_id=settings.requirement_confirmation_agent_id,
            next_stage_code="creative_direction",
        ),
        "creative_direction": StageDefinition(
            stage_code="creative_direction",
            title="策划方向",
            agent_id=settings.creative_direction_agent_id,
            next_stage_code="proposal_generation",
        ),
        "proposal_generation": StageDefinition(
            stage_code="proposal_generation",
            title="方案生成",
            agent_id=settings.proposal_generation_agent_id,
            next_stage_code="feedback_revision",
        ),
        "feedback_revision": StageDefinition(
            stage_code="feedback_revision",
            title="反馈修改",
            agent_id=settings.feedback_revision_agent_id,
            next_stage_code=None,
        ),
    }


def get_stage_definition(stage_code: str) -> StageDefinition:
    """查询阶段定义，不允许使用未注册阶段推进流程。"""
    definition = get_stage_definitions().get(stage_code)
    if definition is None:
        raise BusinessException(409, f"未注册的工作流阶段: {stage_code}")
    return definition


def get_next_stage_definition(stage_code: str) -> StageDefinition:
    """根据当前阶段返回后端固定配置的下一阶段。"""
    current = get_stage_definition(stage_code)
    if current.next_stage_code is None:
        raise BusinessException(409, "当前已经是最后阶段，不能继续进入下一步")
    return get_stage_definition(current.next_stage_code)
