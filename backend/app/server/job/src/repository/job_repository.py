from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.server.job.src.models.job_model import (
    JobDirection,
    JobMarketProfile,
    JobPosting,
    JobRawRecord,
    SpiderCrawlRun,
)


class JobRepository:
    """岗位库数据访问层。"""

    def create_crawl_run(self, crawl_run: SpiderCrawlRun, db: Session) -> SpiderCrawlRun:
        """
        创建一次爬虫运行记录。

        Args:
            crawl_run: 待保存的爬虫运行记录。
            db: 数据库会话。
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
        保存一条岗位原始数据。

        Args:
            raw_record: 原始岗位数据模型。
            db: 数据库会话。
        """
        db.add(raw_record)
        try:
            db.commit()
            db.refresh(raw_record)
            return raw_record
        except IntegrityError:
            # 如果 job_raw_records.content_hash 设置了唯一索引，重复采集时会进入这里。
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
        """
        if not content_hash:
            return None
        sql = select(JobRawRecord).where(JobRawRecord.content_hash == content_hash)
        return db.exec(sql).first()

    def find_posting_for_upsert(
        self,
        platform: str,
        platform_job_id: str | None,
        source_url: str | None,
        db: Session,
    ) -> JobPosting | None:
        """
        按平台岗位 ID 或来源 URL 查找已有岗位，用于主表去重更新。

        Args:
            platform: 招聘平台标识。
            platform_job_id: 招聘平台岗位 ID。
            source_url: 招聘详情页 URL。
            db: 数据库会话。
        """
        # 优先使用平台岗位 ID，因为它通常比 URL 更稳定。
        if platform_job_id:
            sql = select(JobPosting).where(
                JobPosting.platform == platform,
                JobPosting.platform_job_id == platform_job_id,
            )
            posting = db.exec(sql).first()
            if posting:
                return posting

        # 平台岗位 ID 不存在或未命中时，使用来源 URL 作为次级唯一标识。
        if source_url:
            sql = select(JobPosting).where(
                JobPosting.platform == platform,
                JobPosting.source_url == source_url,
            )
            return db.exec(sql).first()

        return None

    def save_posting(self, posting: JobPosting, db: Session) -> JobPosting:
        """
        新增或更新岗位主表记录。

        Args:
            posting: 岗位主表模型。
            db: 数据库会话。
        """
        db.add(posting)
        db.commit()
        db.refresh(posting)
        return posting

    def get_posting_by_id(self, job_id: int, db: Session) -> JobPosting | None:
        """
        根据岗位 ID 查询岗位详情。

        Args:
            job_id: 岗位主表 ID。
            db: 数据库会话。
        """
        return db.get(JobPosting, job_id)

    def list_postings(
        self,
        db: Session,
        *,
        keyword: str | None = None,
        city: str | None = None,
        platform: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[JobPosting], int]:
        """
        分页查询岗位主表。

        Args:
            db: 数据库会话。
            keyword: 岗位标题关键词。
            city: 城市筛选。
            platform: 平台筛选。
            status: 岗位状态筛选。
            page: 当前页码。
            page_size: 每页数量。
        """
        filters = []
        if keyword:
            filters.append(col(JobPosting.job_title_raw).ilike(f"%{keyword}%"))
        if city:
            filters.append(JobPosting.city == city)
        if platform:
            filters.append(JobPosting.platform == platform)
        if status:
            filters.append(JobPosting.status == status)

        base_sql = select(JobPosting)
        count_sql = select(func.count()).select_from(JobPosting)
        for query_filter in filters:
            base_sql = base_sql.where(query_filter)
            count_sql = count_sql.where(query_filter)

        # 最新采集到的岗位优先展示，方便岗位库直接用于人工检查。
        offset = (page - 1) * page_size
        list_sql = base_sql.order_by(JobPosting.last_seen_at.desc()).offset(offset).limit(page_size)
        rows = list(db.exec(list_sql).all())
        total = db.exec(count_sql).one()
        return rows, int(total)

    def list_raw_records_by_job(
        self,
        job: JobPosting,
        db: Session,
        *,
        limit: int = 20,
    ) -> list[JobRawRecord]:
        """
        查询某个岗位对应的最近原始采集记录。

        Args:
            job: 岗位主表记录。
            db: 数据库会话。
            limit: 返回数量上限。
        """
        filters = [JobRawRecord.platform == job.platform]
        if job.platform_job_id:
            filters.append(JobRawRecord.platform_job_id == job.platform_job_id)
        elif job.source_url:
            filters.append(JobRawRecord.source_url == job.source_url)
        else:
            return []

        sql = (
            select(JobRawRecord)
            .where(*filters)
            .order_by(JobRawRecord.collected_at.desc())
            .limit(limit)
        )
        return list(db.exec(sql).all())

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
        分页查询平台岗位方向。

        Args:
            db: 数据库会话。
            keyword: 岗位方向关键词，会匹配名称、编码和描述。
            status: 岗位方向状态，例如 active。
            page: 当前页码。
            page_size: 每页数量。
        """
        filters = []
        if keyword:
            like_keyword = f"%{keyword}%"
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
        """
        return db.get(JobDirection, direction_id)

    def get_profile_by_direction_id(self, direction_id: int, db: Session) -> JobMarketProfile | None:
        """
        根据岗位方向 ID 查询聚合岗位画像。

        Args:
            direction_id: 岗位方向 ID。
            db: 数据库会话。
        """
        sql = select(JobMarketProfile).where(JobMarketProfile.direction_id == direction_id)
        return db.exec(sql).first()
