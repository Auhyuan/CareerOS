from uuid import uuid4

from app.server.agent.src.runtime.context import AgentRuntimeContext
from app.server.agent.src.runtime.context_schema import create_agent_context_schema
from app.server.agent.src.schemas.request import AgentRunRequest


class AgentRuntimeContextService:
    """Agent 运行上下文服务。"""

    def build_context(self, request: AgentRunRequest) -> AgentRuntimeContext:
        """根据运行请求构建 Agent 运行上下文。

        Args:
            request: 通用 Agent 运行请求。

        Returns:
            AgentRuntimeContext 运行上下文对象。
        """
        thread_id = request.conversation_id or uuid4().hex
        optional_features = request.optional_features.model_dump()

        return AgentRuntimeContext(
            thread_id=thread_id,
            query=request.query,
            sys_var={"thread_id": thread_id},
            user_var=request.inputs,
            inputs=request.inputs,
            files=request.files,
            allowed_tools=request.tools,
            optional_features=optional_features,
            memory_enabled=request.optional_features.long_term_memory_enabled,
        )

    def get_context_schema(self):
        """获取 LangChain Agent 运行时上下文 schema。

        Returns:
            可传给 create_agent(context_schema=...) 的 Pydantic 模型类。
        """
        return create_agent_context_schema()
