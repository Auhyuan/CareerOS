from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime

from app.common.db.postgres_db import get_db_session
from app.server.file.src.service.file_service import FileService


def _get_allowed_file_ids(runtime: ToolRuntime) -> set[str]:
    """从 ToolRuntime.context 中读取本次 Agent 允许访问的附件 ID。

    Args:
        runtime: LangGraph 注入的工具运行时对象。

    Returns:
        本次请求允许读取的 file_id 集合。
    """
    context = getattr(runtime, "context", None) if runtime is not None else None
    if isinstance(context, dict):
        file_ids = context.get("file_ids") or []
    elif hasattr(context, "model_dump"):
        file_ids = context.model_dump().get("file_ids") or []
    else:
        file_ids = []
    if not isinstance(file_ids, list):
        return set()
    return {str(file_id).strip() for file_id in file_ids if str(file_id or "").strip()}


@tool("read_uploaded_file")
async def read_uploaded_file(file_id: str, runtime: ToolRuntime) -> str:
    """读取本次请求中用户上传的单个文件内容。

    重要限制：
    1. 每次只能读取一个 file_id。
    2. 只能读取本次 Agent 请求 file_ids 白名单中的文件。
    3. 如果需要查看多个文件，必须多次调用本工具。

    Args:
        file_id: 要读取的单个附件文件 ID。
        runtime: LangGraph 注入的工具运行时，用于读取本次允许访问的 file_ids。

    Returns:
        文件解析后的文本内容，或明确的错误说明。
    """
    cleaned_file_id = str(file_id or "").strip()
    if not cleaned_file_id:
        return "错误：file_id 不能为空。"

    allowed_file_ids = _get_allowed_file_ids(runtime)
    if cleaned_file_id not in allowed_file_ids:
        return "错误：该文件不在本次请求允许访问的附件列表中，不能读取。"

    # 文件解析由 FileService 统一负责。parse_file 会优先复用 parsed_text 缓存，避免重复解析。
    with get_db_session() as db:
        parsed = await FileService().parse_file(db, file_id=cleaned_file_id, parse_mode="text", force=False)

    if not parsed.content.strip():
        return f"文件 {parsed.original_name} 已读取，但没有解析到可用文本内容。"

    return (
        f"文件ID：{parsed.file_id}\n"
        f"文件名：{parsed.original_name}\n"
        f"解析模式：{parsed.parse_mode}\n"
        f"文本长度：{parsed.content_length}\n\n"
        f"{parsed.content}"
    )
