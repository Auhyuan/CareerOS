import os
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlmodel import Session

from app.server.file.src.models.file_models import UploadedFileRecord
from app.server.file.src.parser.file_parser import FileParser
from app.server.file.src.repository.file_repository import FileRepository
from app.server.file.src.schemas.file_schemas import (
    AgentFileContext,
    FileDeleteResponse,
    FileParseResponse,
    FileUploadResponse,
    UploadedFileView,
)


class FileService:
    """文件服务，负责上传、存储、解析和删除文件。"""

    def __init__(self, repository: FileRepository | None = None, parser: FileParser | None = None):
        """初始化文件服务。"""
        self.repository = repository or FileRepository()
        self.parser = parser or FileParser()

    def upload_files(self, db: Session, files: list[UploadFile]) -> FileUploadResponse:
        """上传多个文件并写入数据库记录。"""
        upload_dir = self.get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)

        uploaded: list[UploadedFileView] = []
        for upload_file in files:
            original_name = upload_file.filename or "unknown"
            extension = Path(original_name).suffix.lower()
            file_id = uuid4().hex
            stored_name = f"{file_id}{extension}"
            storage_path = upload_dir / stored_name

            # 将上传流复制到本地磁盘。这里使用同步写入，FastAPI 会把 UploadFile 包装成文件对象。
            with storage_path.open("wb") as target:
                shutil.copyfileobj(upload_file.file, target)

            record = UploadedFileRecord(
                file_id=file_id,
                original_name=original_name,
                stored_name=stored_name,
                storage_path=str(storage_path),
                extension=extension,
                mime_type=upload_file.content_type,
                size_bytes=storage_path.stat().st_size,
                status="uploaded",
                parse_status="pending",
                extra_metadata={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            uploaded.append(self.to_view(self.repository.add(db, record)))

        return FileUploadResponse(files=uploaded)

    def get_upload_dir(self) -> Path:
        """获取文件上传目录。"""
        configured_dir = os.getenv("AI_BACKEND_UPLOAD_DIR") or os.getenv("UPLOAD_DIR")
        if configured_dir:
            return Path(configured_dir).resolve()
        return Path(__file__).resolve().parents[5] / "data" / "uploads"

    def get_file(self, db: Session, file_id: str) -> UploadedFileView:
        """查询文件详情。"""
        record = self.repository.get_by_id(db, file_id)
        if record is None:
            raise RuntimeError(f"文件不存在: {file_id}")
        return self.to_view(record)

    async def parse_file(self, db: Session, file_id: str, parse_mode: str = "text", force: bool = False) -> FileParseResponse:
        """解析文件为文本内容。"""
        record = self.repository.get_by_id(db, file_id)
        if record is None:
            raise RuntimeError(f"文件不存在: {file_id}")

        if record.parsed_text and not force:
            return self.to_parse_response(record, parse_mode, record.parsed_text)

        try:
            content = await self.parser.parse_to_text(record.storage_path, record.extension)
            record.parsed_text = content
            record.parse_status = "success"
            record.parse_error = None
        except Exception as error:
            record.parse_status = "failed"
            record.parse_error = str(error)
            record.updated_at = datetime.now()
            self.repository.update(db, record)
            raise

        record.updated_at = datetime.now()
        self.repository.update(db, record)
        return self.to_parse_response(record, parse_mode, content)

    async def build_agent_file_contexts(self, db: Session, file_ids: list[str]) -> list[AgentFileContext]:
        """根据附件文件 ID 列表构建 Agent 可读取的文件上下文。

        Args:
            db: PostgreSQL Session。
            file_ids: 前端通过 /file/upload 获取到的文件 ID 列表。

        Returns:
            Agent 可注入模型上下文的文件内容列表。
        """
        contexts: list[AgentFileContext] = []
        for raw_file_id in file_ids or []:
            file_id = str(raw_file_id or "").strip()
            if not file_id:
                continue

            # 当前接口只暴露 file_id，解析策略固定为 text，且优先使用 parsed_text 缓存。
            # 后续如果需要强制重新解析或多解析模式，再单独扩展接口，不在 MVP 请求体里增加复杂对象。
            parsed = await self.parse_file(db, file_id=file_id, parse_mode="text", force=False)
            contexts.append(AgentFileContext(
                file_id=parsed.file_id,
                file_name=parsed.original_name,
                content=parsed.content,
                metadata={"parse_mode": "text", "content_length": parsed.content_length},
            ))
        return contexts

    def list_agent_file_summaries(self, db: Session, file_ids: list[str]) -> list[dict[str, object]]:
        """查询本次 Agent 可访问附件的元信息清单。

        Args:
            db: PostgreSQL Session。
            file_ids: 前端通过 /file/upload 获取到的文件 ID 列表。

        Returns:
            附件元信息列表。这里只返回文件清单，不返回正文内容。
        """
        cleaned_ids = [str(file_id or "").strip() for file_id in file_ids or [] if str(file_id or "").strip()]
        if not cleaned_ids:
            return []

        records = self.repository.list_by_ids(db, cleaned_ids)
        record_map = {record.file_id: record for record in records}
        summaries: list[dict[str, object]] = []
        for file_id in cleaned_ids:
            record = record_map.get(file_id)
            if record is None:
                summaries.append({"file_id": file_id, "status": "missing"})
                continue
            summaries.append({
                "file_id": record.file_id,
                "original_name": record.original_name,
                "extension": record.extension,
                "mime_type": record.mime_type,
                "size_bytes": record.size_bytes,
                "status": record.status,
                "parse_status": record.parse_status,
            })
        return summaries

    def delete_files(self, db: Session, file_ids: list[str]) -> FileDeleteResponse:
        """删除文件记录和磁盘文件。"""
        records = self.repository.list_by_ids(db, file_ids)
        deleted_ids: list[str] = []
        for record in records:
            path = Path(record.storage_path)
            if path.exists():
                path.unlink()
            deleted_ids.append(record.file_id)
        deleted = self.repository.delete_by_ids(db, deleted_ids)
        return FileDeleteResponse(deleted=deleted, file_ids=deleted_ids)

    def to_view(self, record: UploadedFileRecord) -> UploadedFileView:
        """把数据库模型转换为接口视图。"""
        return UploadedFileView(
            file_id=record.file_id,
            original_name=record.original_name,
            stored_name=record.stored_name,
            extension=record.extension,
            mime_type=record.mime_type,
            size_bytes=record.size_bytes,
            status=record.status,
            parse_status=record.parse_status,
            created_at=record.created_at.isoformat() if record.created_at else None,
            updated_at=record.updated_at.isoformat() if record.updated_at else None,
        )

    def to_parse_response(self, record: UploadedFileRecord, parse_mode: str, content: str) -> FileParseResponse:
        """构建文件解析响应。"""
        return FileParseResponse(
            file_id=record.file_id,
            original_name=record.original_name,
            parse_mode=parse_mode,
            content=content,
            content_length=len(content or ""),
            parse_status=record.parse_status,
        )
