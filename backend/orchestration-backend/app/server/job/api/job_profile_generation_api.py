from typing import Any

from fastapi import APIRouter

from app.common.schemas.result import Result


router = APIRouter(prefix="/profiles")


@router.post("/generate", response_model=Result[dict[str, Any]], summary="生成岗位画像，占位接口")
def generate_job_profile_placeholder():
    """
    岗位画像生成占位接口。

    后续这里会编排岗位样本查询、Agent 分析、结构化结果校验和岗位画像入库流程。

    Returns:
        当前占位状态。
    """
    return Result.success(
        {
            "status": "planned",
            "message": "岗位画像生成流程尚未实现，当前接口仅作为 API 分块占位。",
        }
    )
