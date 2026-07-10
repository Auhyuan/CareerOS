from pydantic import BaseModel, Field, field_validator


class ContextSummarizationConfig(BaseModel):
    """Agent 模板中的会话上下文总结配置。

    模板存在该对象即表示启用会话总结；没有该对象时不装配总结中间件。
    """

    model_code: str = Field(..., min_length=1, max_length=100, description="用于会话总结的已启用 chat 模型编码")
    trigger_tokens: int = Field(default=12000, ge=1, description="达到该 Token 数后触发总结")
    keep_messages: int = Field(default=20, ge=1, description="总结后保留的近期消息数量")
    trim_tokens_to_summarize: int = Field(default=4000, ge=1, description="单次总结请求最多携带的 Token 数")

    @field_validator("model_code")
    @classmethod
    def normalize_model_code(cls, value: str) -> str:
        """清理总结模型编码两侧空白，避免保存空配置。"""
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("model_code 不能为空")
        return cleaned_value
