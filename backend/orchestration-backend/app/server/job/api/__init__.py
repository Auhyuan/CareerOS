from fastapi import APIRouter

from app.server.job.api.health_api import router as health_router
from app.server.job.api.job_crawl_api import router as job_crawl_router
from app.server.job.api.job_direction_api import router as job_direction_router
from app.server.job.api.job_profile_api import router as job_profile_router
from app.server.job.api.job_raw_record_api import router as job_raw_record_router


router = APIRouter()

# Job 模块 API 按业务对象拆分：原始岗位、岗位方向、岗位画像、采集编排。
router.include_router(health_router)
router.include_router(job_crawl_router)
router.include_router(job_direction_router)
router.include_router(job_raw_record_router)
router.include_router(job_profile_router)

__all__ = ["router"]
