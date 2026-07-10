import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

from app.common.db.postgres_db import get_db_session
from app.server.agent.src.graph.state import CareerAgentState
from app.server.file.src.service.file_service import FileService

logger = logging.getLogger(__name__)


class FileContextMiddleware(AgentMiddleware[CareerAgentState]):
    """附件上下文中间件，负责把可访问附件清单注入模型上下文。"""

    def __init__(self, file_service: FileService | None = None):
        """初始化附件上下文中间件。

        Args:
            file_service: 文件服务实例，不传时自动创建默认文件服务。
        """
        self.file_service = file_service or FileService()

    def _get_runtime_context(self, request: ModelRequest) -> Any:
        """读取 LangChain runtime context。

        Args:
            request: LangChain 模型调用请求。

        Returns:
            本次 Agent 运行上下文；可能是 dict，也可能是 Pydantic 对象。
        """
        return getattr(request.runtime, "context", None)

    def _get_file_ids(self, request: ModelRequest) -> list[str]:
        """从 runtime context 中读取附件文件 ID 列表。

        Args:
            request: LangChain 模型调用请求。

        Returns:
            附件文件 ID 列表。没有附件时返回空列表。
        """
        context = self._get_runtime_context(request)
        if isinstance(context, dict):
            file_ids = context.get("file_ids") or []
        else:
            file_ids = getattr(context, "file_ids", []) or []
        if not isinstance(file_ids, list):
            return []
        return [str(file_id).strip() for file_id in file_ids if str(file_id or "").strip()]

    def _get_run_id(self, request: ModelRequest) -> str:
        """从 runtime context 中读取 run_id，方便日志排查。

        Args:
            request: LangChain 模型调用请求。

        Returns:
            当前 Agent run_id。读取不到时返回空字符串。
        """
        context = self._get_runtime_context(request)
        if isinstance(context, dict):
            return str(context.get("run_id") or "")
        return str(getattr(context, "run_id", "") or "")

    def _format_file_list(self, file_summaries: list[dict[str, object]]) -> str:
        """把附件元信息格式化为模型可读的文件清单。

        Args:
            file_summaries: 文件元信息列表。

        Returns:
            文件清单文本，不包含文件正文。
        """
        lines: list[str] = []
        for index, item in enumerate(file_summaries, start=1):
            file_id = str(item.get("file_id") or "")
            if item.get("status") == "missing":
                lines.append(f"{index}. file_id={file_id}; status=missing")
                continue
            lines.append(
                "{index}. file_id={file_id}; name={name}; extension={extension}; "
                "mime_type={mime_type}; size_bytes={size_bytes}; parse_status={parse_status}".format(
                    index=index,
                    file_id=file_id,
                    name=str(item.get("original_name") or ""),
                    extension=str(item.get("extension") or ""),
                    mime_type=str(item.get("mime_type") or ""),
                    size_bytes=str(item.get("size_bytes") or 0),
                    parse_status=str(item.get("parse_status") or ""),
                )
            )
        return "\n".join(lines)

    def _build_file_list_text(self, file_ids: list[str]) -> str:
        """查询并格式化本次请求的附件清单。

        Args:
            file_ids: Agent 请求中的附件文件 ID 列表。

        Returns:
            附件清单文本。没有可用附件时返回空字符串。
        """
        with get_db_session() as db:
            summaries = self.file_service.list_agent_file_summaries(db, file_ids)
        return self._format_file_list(summaries)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """在模型调用前注入附件清单。

        Args:
            request: LangChain 模型调用请求。
            handler: 下一个模型调用处理器。

        Returns:
            模型响应。没有附件时原样透传。
        """
        file_ids = self._get_file_ids(request)
        if not file_ids:
            return await handler(request)

        file_list_text = self._build_file_list_text(file_ids)
        if not file_list_text:
            return await handler(request)

        run_id = self._get_run_id(request)
        logger.info("附件清单注入成功: run_id=%s file_ids=%s", run_id, len(file_ids))

        # 这里只注入清单，不注入正文。正文必须由 read_uploaded_file 工具按单个 file_id 读取。
        inserted = (
            "\n\n<uploaded_files>\n"
            "用户本轮上传了以下附件。这里仅提供文件清单，不包含文件正文。\n"
            "如果用户要求查看、总结、分析、比较附件内容，必须先调用 read_uploaded_file 读取对应文件。\n"
            "read_uploaded_file 每次只能读取一个 file_id；如需查看多个文件，必须分多次调用。\n"
            "不得在未读取文件内容前声称已经查看或分析了附件正文。\n\n"
            f"{file_list_text}\n"
            "</uploaded_files>"
        )
        current_prompt = getattr(request.system_message, "content", "")
        new_system = SystemMessage(content=f"{current_prompt}{inserted}")
        return await handler(request.override(system_message=new_system))
