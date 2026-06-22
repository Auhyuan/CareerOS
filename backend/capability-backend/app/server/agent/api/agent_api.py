from fastapi import APIRouter, Depends
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
            ],
        )
    )


@router.post("/run", response_model=Result[AgentRunResponse], summary="运行通用 Agent")
async def run_agent(request: AgentRunRequest, db: Session = Depends(get_postgres_engine)):
    """运行通用 Agent。

    Args:
        request: Agent 运行请求。通过 tools 控制本次可用工具，通过 inputs 注入业务变量。
        db: PostgreSQL Session，用于按需读写会话上下文。

    Returns:
        Agent 运行结果。
    """
    result = await agent_service.run(request, db)
    return Result.success(result)
