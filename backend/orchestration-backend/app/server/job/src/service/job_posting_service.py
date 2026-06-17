from typing import Any

from sqlmodel import Session

from app.server.job.src.config.job_config import JOB_DEFAULT_PAGE, JOB_DEFAULT_PAGE_SIZE, JOB_MAX_PAGE_SIZE
from app.server.job.src.models.job_model import JobPosting, JobRawRecord
from app.server.job.src.repository.job_repository import JobRepository


class JobPostingService:
    """标准岗位和原始岗位记录查询服务。"""

    def __init__(self, repository: JobRepository | None = None):
        """
        初始化岗位查询服务。

        Args:
            repository: 岗位库数据访问对象。
        """
        self.repository = repository or JobRepository()

    def list_postings(
        self,
        db: Session,
        *,
        keyword: str | None = None,
        city: str | None = None,
        platform: str | None = None,
        status: str | None = None,
        page: int = JOB_DEFAULT_PAGE,
        page_size: int = JOB_DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        """
        分页查询岗位库。

        Args:
            db: 数据库会话。
            keyword: 岗位标题关键词。
            city: 城市筛选。
            platform: 平台筛选。
            status: 岗位状态筛选。
            page: 页码。
            page_size: 每页数量。

        Returns:
            岗位分页结果。
        """
        safe_page = max(page, 1)
        safe_page_size = min(max(page_size, 1), JOB_MAX_PAGE_SIZE)
        rows, total = self.repository.list_postings(
            db,
            keyword=keyword,
            city=city,
            platform=platform,
            status=status,
            page=safe_page,
            page_size=safe_page_size,
        )
        return {
            "items": rows,
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
        }

    def get_posting_detail(self, db: Session, job_id: int) -> JobPosting | None:
        """
        查询岗位详情。

        Args:
            db: 数据库会话。
            job_id: 岗位主表 ID。

        Returns:
            岗位详情；不存在时返回 None。
        """
        return self.repository.get_posting_by_id(job_id, db)

    def list_raw_records_by_job(self, db: Session, job_id: int, limit: int = 20) -> list[JobRawRecord]:
        """
        查询某个岗位最近的原始采集记录。

        Args:
            db: 数据库会话。
            job_id: 岗位主表 ID。
            limit: 返回数量上限。

        Returns:
            原始采集记录列表。
        """
        job = self.repository.get_posting_by_id(job_id, db)
        if job is None:
            return []
        return self.repository.list_raw_records_by_job(job, db, limit=limit)
