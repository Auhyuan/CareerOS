from typing import Any

from sqlmodel import Session

from app.server.job.src.config.job_config import JOB_DEFAULT_PAGE, JOB_DEFAULT_PAGE_SIZE, JOB_MAX_PAGE_SIZE
from app.server.job.src.models.job_model import JobDirection
from app.server.job.src.repository.job_repository import JobRepository


class JobDirectionService:
    """岗位方向服务，负责岗位方向字典的查询能力。"""

    def __init__(self, repository: JobRepository | None = None):
        """
        初始化岗位方向服务。
        Args:
            repository: 岗位库数据访问对象。
        """
        self.repository = repository or JobRepository()

    def list_directions(
        self,
        db: Session,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = JOB_DEFAULT_PAGE,
        page_size: int = JOB_DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        """
        分页查询平台岗位方向字典。
        Args:
            db: 数据库会话。
            keyword: 岗位方向关键字。
            status: 岗位方向状态。
            page: 页码。
            page_size: 每页数量。
        Returns:
            岗位方向分页结果。
        """
        safe_page = max(page, 1)
        safe_page_size = min(max(page_size, 1), JOB_MAX_PAGE_SIZE)
        rows, total = self.repository.list_directions(
            db,
            keyword=keyword,
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

    def get_direction_detail(self, db: Session, direction_id: int) -> JobDirection | None:
        """
        查询岗位方向详情。
        Args:
            db: 数据库会话。
            direction_id: 岗位方向 ID。
        Returns:
            岗位方向详情；不存在时返回 None。
        """
        return self.repository.get_direction_by_id(direction_id, db)
