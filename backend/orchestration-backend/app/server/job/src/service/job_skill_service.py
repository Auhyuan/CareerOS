import re
import unicodedata

from sqlmodel import Session

from app.server.job.src.repository.job_skill_repository import JobSkillRepository
from app.server.job.src.schemas.job_skill import (
    JobSkillBatchDeleteRequest,
    JobSkillBatchDeleteResponse,
    JobSkillCreateRequest,
    JobSkillCreateResponse,
    JobSkillResponse,
    JobSkillSearchRequest,
    JobSkillSearchResponse,
)


class JobSkillService:
    """岗位技能服务，负责标准化、查询、查重和创建技能。"""

    def __init__(self, repository: JobSkillRepository | None = None):
        """
        初始化岗位技能服务。

        Args:
            repository: 岗位技能数据访问对象。
        """
        self.repository = repository or JobSkillRepository()

    def search_skills(self, db: Session, request: JobSkillSearchRequest) -> JobSkillSearchResponse:
        """
        查询与关键字相关的岗位技能。

        Args:
            db: 数据库会话。
            request: 技能查询条件。

        Returns:
            匹配到的岗位技能列表。
        """
        normalized_keyword = self.normalize_skill_name(request.keyword)
        rows = self.repository.search(
            db,
            keyword=request.keyword,
            normalized_keyword=normalized_keyword,
            limit=request.limit,
        )
        items = [JobSkillResponse.model_validate(row) for row in rows]
        return JobSkillSearchResponse(items=items, total=len(items))

    def create_skill(self, db: Session, request: JobSkillCreateRequest) -> JobSkillCreateResponse:
        """
        创建岗位技能；标准化名称已存在时直接复用已有技能。

        Args:
            db: 数据库会话。
            request: 技能名称和描述。

        Returns:
            创建或复用的技能，以及本次是否真正创建。
        """
        normalized_name = self.normalize_skill_name(request.name)
        skill, created = self.repository.create_or_get(
            db,
            name=request.name,
            normalized_name=normalized_name,
            description=request.description,
        )
        return JobSkillCreateResponse(
            skill=JobSkillResponse.model_validate(skill),
            created=created,
        )

    def delete_skills(self, db: Session, request: JobSkillBatchDeleteRequest) -> JobSkillBatchDeleteResponse:
        """
        批量删除岗位技能。

        对于请求中不存在的技能 ID，会放入 missing_ids 一起返回，不抛异常，
        方便前端一次性提示用户哪些 ID 已经失效。

        Args:
            db: 数据库会话。
            request: 批量删除请求，包含去重后的技能 ID 列表。

        Returns:
            批量删除结果，包含已删除 ID 和缺失 ID。
        """
        existing_skills = self.repository.list_by_ids(db, request.skill_ids)
        existing_ids = {skill.id for skill in existing_skills}
        missing_ids = [skill_id for skill_id in request.skill_ids if skill_id not in existing_ids]
        deleted_ids = sorted(existing_ids)

        if existing_skills:
            self.repository.delete_skills(db, existing_skills)

        return JobSkillBatchDeleteResponse(
            requested=len(request.skill_ids),
            deleted=len(deleted_ids),
            deleted_ids=deleted_ids,
            missing_ids=missing_ids,
        )

    @staticmethod
    def normalize_skill_name(name: str) -> str:
        """
        将技能名称转换为稳定的查重键。

        Args:
            name: 原始技能名称。

        Returns:
            Unicode 统一、转小写并移除常见分隔符后的名称。
        """
        normalized = unicodedata.normalize("NFKC", name).casefold().strip()
        return re.sub(r"[\s._-]+", "", normalized)
