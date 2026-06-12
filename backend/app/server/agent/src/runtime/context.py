from typing import Any

from pydantic import BaseModel, Field


class AgentRuntimeContext(BaseModel):
    """Agent 单次运行上下文。"""

    agent_name: str = Field(default="default", description="Agent 名称")
    thread_id: str = Field(default="", description="会话线程 ID")
    query: str = Field(default="", description="本次运行的用户问题或任务指令")
    sys_var: dict[str, Any] = Field(default_factory=dict, description="系统变量，例如 user_id、request_id")
    user_var: dict[str, Any] = Field(default_factory=dict, description="用户变量或编排层输入变量")
    inputs: dict[str, Any] = Field(default_factory=dict, description="业务输入变量")
    files: list[dict[str, Any]] = Field(default_factory=list, description="附件上下文")
    input_messages: list[dict[str, Any]] = Field(default_factory=list, description="历史输入消息")
    allowed_tools: list[str] = Field(default_factory=list, description="本次运行允许调用的工具")
    optional_features: dict[str, Any] = Field(default_factory=dict, description="本次运行开启的增强能力")
    memory_enabled: bool = Field(default=False, description="本次运行是否启用长期记忆")
    metadata: dict[str, Any] = Field(default_factory=dict, description="运行元数据")

    def to_langchain_context(self) -> dict[str, Any]:
        """
        转换为 LangChain Agent runtime context。

        Returns:
            可传给 LangChain agent.ainvoke(..., context=...) 的字典。
        """
        return self.model_dump()
