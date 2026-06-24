import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.agent.src.agent import AgentService
from app.server.agent.src.model import get_model_config
from app.server.agent.src.schemas.request import AgentRunRequest
from app.server.agent.src.schemas.response import AgentCapabilityResponse, AgentRunResponse, ModelConfigResponse


router = APIRouter()
agent_service = AgentService()


@router.get("/health", response_model=Result[dict], summary="Agent 服务健康检查")
def agent_health():
    """检查 Agent 服务是否已经挂载。

    Returns:
        Agent 服务的基础运行状态。
    """
    return Result.success({"service": "agent", "status": "ok"})


@router.get("/model/config", response_model=Result[ModelConfigResponse], summary="查询当前模型配置")
def get_current_model_config():
    """查询当前 Agent 服务使用的模型连接配置。

    Returns:
        去除密钥后的模型网关配置，方便确认 YAML 路径、默认模型和可用别名。
    """
    config = get_model_config()
    return Result.success(
        ModelConfigResponse(
            gateway_path=config.gateway_path,
            available_models=sorted(config.models),
            provider=config.provider,
            base_url=config.base_url,
            chat_model=config.chat_model,
            embedding_model=config.embedding_model,
            rerank_model=config.rerank_model,
            langsmith_tracing=config.langsmith_tracing,
            langsmith_endpoint=config.langsmith_endpoint,
            langsmith_project=config.langsmith_project,
            has_api_key=bool(config.get_api_key()),
            has_langsmith_api_key=bool(config.get_langsmith_api_key()),
        )
    )


@router.get("/capabilities", response_model=Result[AgentCapabilityResponse], summary="查询 Agent 服务能力")
def get_agent_capabilities():
    """查询 Agent 服务当前已经规划好的能力模块。

    Returns:
        Agent 服务的架构能力清单，主要用于确认骨架和边界。
    """
    return Result.success(
        AgentCapabilityResponse(
            service_name="agent",
            modules=[
                "agent",
                "model",
                "schemas",
                "prompts",
                "tools",
                "templates",
                "runtime",
                "middlewares",
                "memory",
                "checkpoint",
                "graph",
            ],
            enabled_features=[
                "openai_compatible_chat_model",
                "embedding_model_placeholder",
                "prompt_rendering",
                "tool_registry_placeholder",
                "agent_template_management",
                "middleware_factory",
                "runtime_context_schema",
                "memory_placeholder",
                "postgres_checkpointer",
                "graph_state_schema",
                "job_skill_http_tools",
            ],
            registered_tools=agent_service.tool_service.list_tools(),
        )
    )


def _format_sse_event(event: dict[str, Any]) -> str:
    """将平台事件字典格式化为 SSE 文本。
    Args:
        event: AgentService.stream 产出的标准化事件。
    Returns:
        符合 text/event-stream 协议的单条事件文本。
    """
    event_type = str(event.get("type") or "message")
    payload = json.dumps(jsonable_encoder(event), ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


@router.post("/run", response_model=Result[AgentRunResponse], summary="运行通用 Agent")
async def run_agent(request: AgentRunRequest, db: Session = Depends(get_postgres_engine)):
    """运行通用 Agent。
    Args:
        request: Agent 运行请求。stream=false 时返回统一 JSON；stream=true 时返回 SSE。
        db: PostgreSQL Session，用于在 conversation_id 非空时写入用户可见会话记录。
    Returns:
        非流式时返回 Agent 运行结果；流式时返回 text/event-stream。
    """
    if request.stream:
        async def event_generator():
            """按 SSE 格式逐条产出 Agent 运行事件。
            Yields:
                已格式化的 SSE 文本片段。
            """
            async for event in agent_service.stream(request, db):
                yield _format_sse_event(event)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        result = await agent_service.run(request, db)
        return Result.success(result)
