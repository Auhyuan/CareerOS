import logging
from typing import Any


logger = logging.getLogger("ai_backend.agent.streaming")


class AgentStreamEventParser:
    """Agent 流式消息解析器。

    该类只负责把 LangGraph messages 流分片转换为平台 SSE 事件，
    不关心 Agent 运行、数据库写入、会话持久化等业务流程。
    """

    def normalize_message_stream_chunk(self, chunk: Any) -> list[dict[str, Any]]:
        """将 LangGraph messages 流分片转换为平台 SSE 事件。

        Args:
            chunk: agent.astream(stream_mode="messages") 产出的分片，通常是 (message, metadata)。

        Returns:
            可序列化的平台事件列表。一个消息分片可能同时包含思考、正文和工具调用。
        """
        message, metadata = self.unpack_message_stream_chunk(chunk)
        if message is None:
            return []

        events: list[dict[str, Any]] = []
        reasoning = self.extract_reasoning_text(message)
        content = self.extract_message_text(message)

        if reasoning:
            events.append({"type": "reasoning_delta", "data": {"content": reasoning}})
        else:
            self.log_reasoning_debug(message)
        if content:
            events.append({"type": "model_delta", "data": {"content": content}})

        for tool_call in self.extract_tool_calls(message):
            events.append({
                "type": "tool_call",
                "data": {
                    "tool_name": tool_call.get("name") or tool_call.get("tool_name") or "tool",
                    "args": self.safe_event_value(tool_call.get("args") or tool_call.get("input") or {}),
                    "id": tool_call.get("id"),
                    "metadata": self.safe_event_value(metadata),
                },
            })
        return events

    def unpack_message_stream_chunk(self, chunk: Any) -> tuple[Any, Any]:
        """解析 messages 流分片，兼容 tuple、list 和 dict 形态。

        Args:
            chunk: LangGraph messages 流返回的原始分片。

        Returns:
            (message, metadata) 二元组；无法解析时 metadata 返回 None。
        """
        if isinstance(chunk, tuple) and chunk:
            message = chunk[0]
            metadata = chunk[1] if len(chunk) > 1 else None
            return message, metadata
        if isinstance(chunk, list) and chunk:
            message = chunk[0]
            metadata = chunk[1] if len(chunk) > 1 else None
            return message, metadata
        if isinstance(chunk, dict):
            return chunk.get("message") or chunk.get("chunk") or chunk.get("messages"), chunk.get("metadata")
        return chunk, None


    def log_reasoning_debug(self, message: Any) -> None:
        """在调试级别记录消息分片中的 reasoning 相关字段位置。

        Args:
            message: LangChain 消息对象或消息分片。
        """
        if not logger.isEnabledFor(logging.DEBUG):
            return
        additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
        response_metadata = getattr(message, "response_metadata", {}) or {}
        content = getattr(message, "content", None)
        logger.debug(
            "流式分片未发现 reasoning: message_type=%s additional_keys=%s metadata_keys=%s content_type=%s",
            message.__class__.__name__,
            sorted(additional_kwargs.keys()),
            sorted(response_metadata.keys()),
            type(content).__name__,
        )

    def extract_tool_calls(self, message: Any) -> list[dict[str, Any]]:
        """从消息分片中提取模型发出的工具调用。

        Args:
            message: LangChain 消息对象或消息分片。

        Returns:
            工具调用字典列表；没有工具调用时返回空列表。
        """
        tool_calls = getattr(message, "tool_calls", None) or []
        if tool_calls:
            return [item for item in tool_calls if isinstance(item, dict)]

        additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
        raw_calls = additional_kwargs.get("tool_calls") or []
        if isinstance(raw_calls, list):
            return [item for item in raw_calls if isinstance(item, dict)]
        return []

    def extract_message_text(self, message: Any) -> str:
        """从模型消息或消息分片中提取普通文本。

        Args:
            message: LangChain 消息对象、消息分片或原生字符串。

        Returns:
            提取出的文本；没有文本时返回空字符串。
        """
        if message is None:
            return ""
        if isinstance(message, str):
            return message

        if isinstance(message, dict):
            content = message.get("content", "")
        else:
            content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                    parts.append(str(item.get("text") or item.get("content") or ""))
            return "".join(parts)
        return ""

    def extract_reasoning_text(self, message: Any) -> str:
        """从模型消息分片中提取供应商返回的思考内容。

        Args:
            message: LangChain 消息对象或消息分片。

        Returns:
            模型供应商显式返回的 reasoning 文本；不支持时返回空字符串。
        """
        if message is None:
            return ""

        if isinstance(message, dict):
            additional_kwargs = message.get("additional_kwargs") or {}
            response_metadata = message.get("response_metadata") or {}
            content = message.get("content")
        else:
            additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
            response_metadata = getattr(message, "response_metadata", {}) or {}
            content = getattr(message, "content", None)

        # DeepSeek 等 OpenAI 兼容思考模型一般把思考内容放在 reasoning_content。
        # 其他供应商可能使用 reasoning / reasoning_text，这里一并兼容。
        for source in (message if isinstance(message, dict) else {}, additional_kwargs, response_metadata):
            if not isinstance(source, dict):
                continue
            for key in ("reasoning_content", "reasoning", "reasoning_text"):
                value = source.get(key)
                if isinstance(value, str) and value:
                    return value

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"reasoning", "thinking"}:
                    parts.append(str(item.get("text") or item.get("content") or ""))
            return "".join(parts)
        return ""

    @staticmethod
    def safe_event_value(obj: Any) -> Any:
        """把 LangChain 内部对象转换为安全的 JSON 值。

        Args:
            obj: 任意 LangChain 对象、Pydantic 模型或 Python 原生值。

        Returns:
            可被 jsonable_encoder / json.dumps 处理的值。
        """
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: AgentStreamEventParser.safe_event_value(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [AgentStreamEventParser.safe_event_value(v) for v in obj]
        if hasattr(obj, "model_dump"):
            return AgentStreamEventParser.safe_event_value(obj.model_dump())
        if hasattr(obj, "dict") and callable(obj.dict):
            return AgentStreamEventParser.safe_event_value(obj.dict())
        return str(obj)
