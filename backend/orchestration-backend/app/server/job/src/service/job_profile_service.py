from sqlmodel import Session

from app.server.job.src.models.job_model import JobMarketProfile
from app.server.job.src.repository.job_repository import JobRepository


class JobProfileService:
    """岗位画像查询服务。"""

    def __init__(self, repository: JobRepository | None = None):
        """
        初始化岗位画像服务。

        Args:
            repository: 岗位库数据访问对象。
        """
        self.repository = repository or JobRepository()

    def get_profile_by_direction_id(self, db: Session, direction_id: int) -> JobMarketProfile | None:
        """
        查询某个岗位方向的聚合画像。

        Args:
            db: 数据库会话。
            direction_id: 岗位方向 ID。

        Returns:
            岗位画像详情；不存在时返回 None。
        """
        return self.repository.get_profile_by_direction_id(direction_id, db)
