from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder

from app.common.schemas.result import Result
from app.server.agent.src.tools import AgentToolService
from app.server.agent.src.tools.schemas import AgentToolInvokeRequest, AgentToolInvokeResponse


router = APIRouter(prefix="/tools")
tool_service = AgentToolService()


@router.post("/invoke", response_model=Result[AgentToolInvokeResponse], summary="调试调用 Agent 工具")
async def invoke_agent_tool(request: AgentToolInvokeRequest):
    """调试调用一个已注册的常规 Agent 工具。

    Args:
        request: 工具名称和工具参数。

    Returns:
        统一响应结构，data 中包含工具执行结果。
    """
    result = await tool_service.invoke_tool(request.tool_name, request.args)
    return Result.success(
        AgentToolInvokeResponse(
            tool_name=request.tool_name,
            args=request.args,
            result=jsonable_encoder(result),
        )
    )
