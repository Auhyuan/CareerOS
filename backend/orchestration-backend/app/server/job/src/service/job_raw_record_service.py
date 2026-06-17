from typing import Any

from sqlmodel import Session

from app.server.job.src.config.job_config import JOB_DEFAULT_PAGE, JOB_DEFAULT_PAGE_SIZE, JOB_MAX_PAGE_SIZE
from app.server.job.src.models.job_model import JobRawRecord
from app.server.job.src.repository.job_repository import JobRepository


class JobRawRecordService:
    """原始岗位池查询服务，供画像生成流程选择招聘样本。"""

    def __init__(self, repository: JobRepository | None = None):
        """
        初始化原始岗位查询服务。
        Args:
            repository: 岗位库数据访问对象。
        """
        self.repository = repository or JobRepository()

    def list_raw_records(
        self,
        db: Session,
        *,
        keyword: str | None = None,
        city: str | None = None,
        platform: str | None = None,
        page: int = JOB_DEFAULT_PAGE,
        page_size: int = JOB_DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        """
        分页查询原始岗位池。
        Args:
            db: 数据库会话。
            keyword: 岗位标题或 JD 正文关键字。
            city: 城市筛选。
            platform: 招聘平台筛选。
            page: 页码。
            page_size: 每页数量。
        Returns:
            原始岗位分页结果。
        """
        safe_page = max(page, 1)
        safe_page_size = min(max(page_size, 1), JOB_MAX_PAGE_SIZE)
        rows, total = self.repository.list_raw_records(
            db,
            keyword=keyword,
            city=city,
            platform=platform,
            page=safe_page,
            page_size=safe_page_size,
        )
        return {
            "items": rows,
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
        }

    def get_raw_record_detail(self, db: Session, raw_record_id: int) -> JobRawRecord | None:
        """
        查询原始岗位详情。
        Args:
            db: 数据库会话。
            raw_record_id: 原始岗位记录 ID。
        Returns:
            原始岗位记录；不存在时返回 None。
        """
        return self.repository.get_raw_record_by_id(raw_record_id, db)
