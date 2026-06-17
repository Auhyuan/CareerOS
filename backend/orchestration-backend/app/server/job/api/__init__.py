from fastapi import APIRouter

from app.server.job.api.health_api import router as health_router
from app.server.job.api.job_crawl_api import router as job_crawl_router
from app.server.job.api.job_direction_api import router as job_direction_router
from app.server.job.api.job_posting_api import router as job_posting_router
from app.server.job.api.job_profile_api import router as job_profile_router
from app.server.job.api.job_profile_generation_api import router as job_profile_generation_router


router = APIRouter()

# Job 模块 API 按业务对象拆分，避免所有接口堆在一个 job_api.py 中。
router.include_router(health_router)
router.include_router(job_crawl_router)
router.include_router(job_direction_router)
router.include_router(job_posting_router)
router.include_router(job_profile_router)
router.include_router(job_profile_generation_router)

__all__ = ["router"]
