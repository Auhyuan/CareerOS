from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.server.job.src.models.job_model import (
    JobDirection,
    JobMarketProfile,
    JobRawRecord,
    SpiderCrawlRun,
)


class JobRepository:
    """岗位模块数据库访问层，统一封装岗位相关表的读写。"""

    def create_crawl_run(self, crawl_run: SpiderCrawlRun, db: Session) -> SpiderCrawlRun:
        """
        创建一次爬虫运行记录。
        Args:
            crawl_run: 待保存的爬虫运行记录。
            db: 数据库会话。
        Returns:
            已保存的爬虫运行记录。
        """
        db.add(crawl_run)
        db.commit()
        db.refresh(crawl_run)
        return crawl_run

    def update_crawl_run(
        self,
        crawl_run_id: int,
        db: Session,
        *,
        status: str,
        total_count: int = 0,
        error_message: str | None = None,
        finished_at: datetime | None = None,
    ) -> SpiderCrawlRun | None:
        """
        更新爬虫运行记录的结束状态。
        Args:
            crawl_run_id: 爬虫运行记录 ID。
            db: 数据库会话。
            status: 本次任务最终状态。
            total_count: 本次任务采集到的岗位数量。
            error_message: 失败原因，成功时为空。
            finished_at: 任务结束时间。
        Returns:
            更新后的爬虫运行记录；记录不存在时返回 None。
        """
        crawl_run = db.get(SpiderCrawlRun, crawl_run_id)
        if crawl_run is None:
            return None

        crawl_run.status = status
        crawl_run.total_count = total_count
        crawl_run.error_message = error_message
        crawl_run.finished_at = finished_at or datetime.now()
        db.add(crawl_run)
        db.commit()
        db.refresh(crawl_run)
        return crawl_run

    def create_raw_record(self, raw_record: JobRawRecord, db: Session) -> JobRawRecord:
        """
        保存一条招聘平台原始岗位记录。
        Args:
            raw_record: 原始岗位数据模型。
            db: 数据库会话。
        Returns:
            已保存的原始岗位记录；如果内容哈希已存在，则返回已有记录。
        """
        db.add(raw_record)
        try:
            db.commit()
            db.refresh(raw_record)
            return raw_record
        except IntegrityError:
            # 如果数据库给 content_hash 建了唯一索引，重复采集会进入这里，直接复用已有原始记录。
            db.rollback()
            existing = self.get_raw_record_by_content_hash(raw_record.content_hash, db)
            if existing:
                return existing
            raise

    def get_raw_record_by_content_hash(self, content_hash: str | None, db: Session) -> JobRawRecord | None:
        """
        根据内容哈希查询原始岗位记录。
        Args:
            content_hash: 原始岗位内容哈希。
            db: 数据库会话。
        Returns:
            命中的原始岗位记录；未命中时返回 None。
        """
        if not content_hash:
            return None
        sql = select(JobRawRecord).where(JobRawRecord.content_hash == content_hash)
        return db.exec(sql).first()

    def get_raw_record_by_id(self, raw_record_id: int, db: Session) -> JobRawRecord | None:
        """
        根据原始岗位记录 ID 查询详情。
        Args:
            raw_record_id: 原始岗位记录 ID。
            db: 数据库会话。
        Returns:
            原始岗位记录详情；不存在时返回 None。
        """
        return db.get(JobRawRecord, raw_record_id)

    def list_raw_records(
        self,
        db: Session,
        *,
        keyword: str | None = None,
        city: str | None = None,
        platform: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[JobRawRecord], int]:
        """
        分页查询原始岗位池。
        Args:
            db: 数据库会话。
            keyword: 岗位标题或 JD 正文关键字。
            city: 城市筛选。
            platform: 招聘平台筛选，例如 qcwy。
            page: 当前页码。
            page_size: 每页数量。
        Returns:
            原始岗位列表和总数。
        """
        filters = []
        if keyword:
            cleaned_keyword = keyword.strip()
            if cleaned_keyword:
                like_keyword = f"%{cleaned_keyword}%"
                filters.append(
                    or_(
                        col(JobRawRecord.raw_title).ilike(like_keyword),
                        col(JobRawRecord.job_description).ilike(like_keyword),
                    )
                )
        if city:
            filters.append(col(JobRawRecord.raw_city).ilike(f"%{city.strip()}%"))
        if platform:
            filters.append(JobRawRecord.platform == platform.strip())

        base_sql = select(JobRawRecord)
        count_sql = select(func.count()).select_from(JobRawRecord)
        for query_filter in filters:
            base_sql = base_sql.where(query_filter)
            count_sql = count_sql.where(query_filter)

        # 原始岗位池默认按采集时间倒序，方便后续画像生成时优先使用最新市场样本。
        offset = (page - 1) * page_size
        list_sql = base_sql.order_by(JobRawRecord.collected_at.desc()).offset(offset).limit(page_size)
        rows = list(db.exec(list_sql).all())
        total = db.exec(count_sql).one()
        return rows, int(total)

    def list_directions(
        self,
        db: Session,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[JobDirection], int]:
        """
        分页查询平台岗位方向字典。
        Args:
            db: 数据库会话。
            keyword: 岗位方向关键字，会匹配名称、编码和描述。
            status: 岗位方向状态，例如 active。
            page: 当前页码。
            page_size: 每页数量。
        Returns:
            岗位方向列表和总数。
        """
        filters = []
        if keyword:
            like_keyword = f"%{keyword.strip()}%"
            filters.append(
                or_(
                    col(JobDirection.name).ilike(like_keyword),
                    col(JobDirection.code).ilike(like_keyword),
                    col(JobDirection.description).ilike(like_keyword),
                )
            )
        if status:
            filters.append(JobDirection.status == status)

        base_sql = select(JobDirection)
        count_sql = select(func.count()).select_from(JobDirection)
        for query_filter in filters:
            base_sql = base_sql.where(query_filter)
            count_sql = count_sql.where(query_filter)

        offset = (page - 1) * page_size
        list_sql = base_sql.order_by(JobDirection.updated_at.desc()).offset(offset).limit(page_size)
        rows = list(db.exec(list_sql).all())
        total = db.exec(count_sql).one()
        return rows, int(total)

    def get_direction_by_id(self, direction_id: int, db: Session) -> JobDirection | None:
        """
        根据岗位方向 ID 查询岗位方向详情。
        Args:
            direction_id: 岗位方向 ID。
            db: 数据库会话。
        Returns:
            岗位方向详情；不存在时返回 None。
        """
        return db.get(JobDirection, direction_id)

    def get_profile_by_id(self, profile_id: int, db: Session) -> JobMarketProfile | None:
        """
        根据岗位画像 ID 查询岗位画像。
        Args:
            profile_id: 岗位画像 ID。
            db: 数据库会话。
        Returns:
            岗位画像；不存在时返回 None。
        """
        return db.get(JobMarketProfile, profile_id)

    def create_profile(self, profile: JobMarketProfile, db: Session) -> JobMarketProfile:
        """
        保存一条岗位画像。
        Args:
            profile: 待保存的岗位画像。
            db: 数据库会话。
        Returns:
            已保存的岗位画像。
        """
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
