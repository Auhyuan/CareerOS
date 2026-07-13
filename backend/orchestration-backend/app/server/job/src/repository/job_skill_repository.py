from dataclasses import dataclass

from sqlalchemy import case, false, func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.server.job.src.models.job_skill_model import JobSkill


@dataclass(frozen=True, slots=True)
class JobSkillSearchMatch:
    """岗位技能查询命中结果，保存技能、命中类型和匹配分数。"""

    skill: JobSkill
    match_type: str
    match_score: int


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
    ) -> list[JobSkillSearchMatch]:
        """
        按名称和描述分层评分查询岗位技能。

        名称精确、前缀和包含命中依次降权，描述命中只用于扩大召回，
        分数明显低于名称命中，避免描述相关候选被误判为同一个技能。

        Args:
            db: 数据库会话。
            keyword: 原始技能查询关键字。
            normalized_keyword: 标准化后的技能关键字。
            limit: 最大返回数量。

        Returns:
            按匹配分数降序排列的技能候选。
        """
        escaped_keyword = self._escape_like_keyword(keyword)
        escaped_normalized = self._escape_like_keyword(normalized_keyword)
        name_prefix_pattern = f"{escaped_keyword}%"
        name_contains_pattern = f"%{escaped_keyword}%"
        normalized_prefix_pattern = f"{escaped_normalized}%"
        normalized_contains_pattern = f"%{escaped_normalized}%"

        # 每种候选只采用命中的最高等级评分。名称相关规则始终高于描述规则。
        # 纯符号关键词标准化后可能为空，此时禁用 normalized_name 规则，避免 LIKE '%' 全表命中。
        normalized_exact = JobSkill.normalized_name == normalized_keyword if normalized_keyword else false()
        name_exact = col(JobSkill.name).ilike(escaped_keyword, escape="\\")
        normalized_prefix = (
            col(JobSkill.normalized_name).like(normalized_prefix_pattern, escape="\\")
            if normalized_keyword
            else false()
        )
        name_prefix = col(JobSkill.name).ilike(name_prefix_pattern, escape="\\")
        normalized_contains = (
            col(JobSkill.normalized_name).like(normalized_contains_pattern, escape="\\")
            if normalized_keyword
            else false()
        )
        name_contains = col(JobSkill.name).ilike(name_contains_pattern, escape="\\")
        description_contains = col(JobSkill.description).ilike(name_contains_pattern, escape="\\")

        match_score = case(
            (normalized_exact, 100),
            (name_exact, 95),
            (normalized_prefix, 85),
            (name_prefix, 80),
            (normalized_contains, 75),
            (name_contains, 70),
            (description_contains, 20),
            else_=0,
        )
        match_type = case(
            (normalized_exact, "normalized_exact"),
            (name_exact, "name_exact"),
            (normalized_prefix, "normalized_prefix"),
            (name_prefix, "name_prefix"),
            (normalized_contains, "normalized_contains"),
            (name_contains, "name_contains"),
            (description_contains, "description_contains"),
            else_="none",
        )

        statement = (
            select(
                JobSkill,
                match_type.label("match_type"),
                match_score.label("match_score"),
            )
            .where(
                or_(
                    normalized_exact,
                    name_exact,
                    normalized_prefix,
                    name_prefix,
                    normalized_contains,
                    name_contains,
                    description_contains,
                )
            )
            .order_by(
                match_score.desc(),
                func.length(JobSkill.name),
                JobSkill.name,
            )
            .limit(limit)
        )
        rows = db.exec(statement).all()
        return [
            JobSkillSearchMatch(
                skill=row[0],
                match_type=str(row[1]),
                match_score=int(row[2]),
            )
            for row in rows
        ]

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

    @staticmethod
    def _escape_like_keyword(value: str) -> str:
        """
        转义 SQL LIKE 模式中的特殊字符，避免关键词被当作通配表达式。

        Args:
            value: 原始或标准化后的查询关键词。

        Returns:
            可安全用于 LIKE / ILIKE 模式的关键词。
        """
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
