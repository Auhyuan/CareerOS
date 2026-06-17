from typing import Any

from fastapi import APIRouter

from app.common.schemas.result import Result


router = APIRouter()


@router.get("/health", response_model=Result[Any], summary="岗位编排服务健康检查")
def job_health():
    """
    检查岗位编排服务是否已经挂载。

    Returns:
        岗位编排服务的基础运行状态。
    """
    return Result.success({"service": "job", "status": "ok"})
