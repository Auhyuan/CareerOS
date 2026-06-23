from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.server.job.src.models.job_skill_model import JobSkill


class JobSkillRepository:
    """岗位技能数据访问层，负责 job_skills 的查询和创建。"""

    def get_by_normalized_name(self, db: Session, normalized_name: str) -> JobSkill | None:
        """
        根据标准化名称精确查询岗位技能。

        Args:
            db: 数据库会话。
            normalized_name: 工具生成的技能标准化名称。

        Returns:
            匹配到的岗位技能；不存在时返回 None。
        """
        statement = select(JobSkill).where(JobSkill.normalized_name == normalized_name)
        return db.exec(statement).first()

    def list_by_ids(self, db: Session, skill_ids: list[int]) -> list[JobSkill]:
        """
        根据技能 ID 列表查询技能，用于批量删除前的存在性校验。

        Args:
            db: 数据库会话。
            skill_ids: 技能 ID 列表。

        Returns:
            数据库中实际存在的技能列表。
        """
        if not skill_ids:
            return []
        statement = select(JobSkill).where(col(JobSkill.id).in_(skill_ids))
        return list(db.exec(statement).all())

    def delete_skills(self, db: Session, skills: list[JobSkill]) -> None:
        """
        批量删除岗位技能。

        Args:
            db: 数据库会话。
            skills: 待删除的技能对象列表。
        """
        for skill in skills:
            db.delete(skill)
        db.commit()

    def search(
        self,
        db: Session,
        *,
        keyword: str,
        normalized_keyword: str,
        limit: int,
    ) -> list[JobSkill]:
        """
        按精确名称、技能名称和描述模糊查询岗位技能。

        Args:
            db: 数据库会话。
            keyword: 原始技能查询关键字。
            normalized_keyword: 标准化后的技能关键字。
            limit: 最大返回数量。

        Returns:
            按精确匹配优先级排序的技能列表。
        """
        like_keyword = f"%{keyword}%"
        statement = (
            select(JobSkill)
            .where(
                or_(
                    JobSkill.normalized_name == normalized_keyword,
                    col(JobSkill.name).ilike(like_keyword),
                    col(JobSkill.description).ilike(like_keyword),
                )
            )
            .order_by(
                case((JobSkill.normalized_name == normalized_keyword, 0), else_=1),
                func.length(JobSkill.name),
                JobSkill.name,
            )
            .limit(limit)
        )
        return list(db.exec(statement).all())

    def create_or_get(
        self,
        db: Session,
        *,
        name: str,
        normalized_name: str,
        description: str,
    ) -> tuple[JobSkill, bool]:
        """
        创建岗位技能，并在并发唯一键冲突时返回已有记录。

        Args:
            db: 数据库会话。
            name: 技能标准名称。
            normalized_name: 技能标准化名称。
            description: 技能描述。

        Returns:
            岗位技能与是否新建成功的标记。
        """
        existing = self.get_by_normalized_name(db, normalized_name)
        if existing is not None:
            return existing, False

        skill = JobSkill(
            name=name,
            normalized_name=normalized_name,
            description=description,
        )
        db.add(skill)
        try:
            db.commit()
            db.refresh(skill)
            return skill, True
        except IntegrityError:
            # 两个 Agent 并发创建同一技能时，由 normalized_name 唯一索引保证最终只保留一条。
            db.rollback()
            existing = self.get_by_normalized_name(db, normalized_name)
            if existing is not None:
                return existing, False
            raise
