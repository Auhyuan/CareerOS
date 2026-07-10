from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from app.common.db.postgres_db import get_postgres_engine
from app.common.schemas.result import Result
from app.server.file.src.schemas.file_schemas import (
    FileDeleteRequest,
    FileDeleteResponse,
    FileDetailRequest,
    FileParseRequest,
    FileParseResponse,
    FileUploadResponse,
    UploadedFileView,
)
from app.server.file.src.service.file_service import FileService


router = APIRouter(prefix="/file")
file_service = FileService()


@router.get("/health", response_model=Result[dict[str, Any]], summary="文件服务健康检查")
def file_health():
    """检查文件服务是否已经挂载。"""
    return Result.success({"service": "file", "status": "ok"})


@router.post("/upload", response_model=Result[FileUploadResponse], summary="上传文件")
def upload_files(files: list[UploadFile] = File(...), db: Session = Depends(get_postgres_engine)):
    """上传文件并返回文件 ID。"""
    result = file_service.upload_files(db, files)
    return Result.success(result)


@router.post("/detail", response_model=Result[UploadedFileView], summary="查询文件详情")
def get_file_detail(request: FileDetailRequest, db: Session = Depends(get_postgres_engine)):
    """根据文件 ID 查询文件详情。"""
    result = file_service.get_file(db, request.file_id)
    return Result.success(result)


@router.post("/parse", response_model=Result[FileParseResponse], summary="解析文件内容")
async def parse_file(request: FileParseRequest, db: Session = Depends(get_postgres_engine)):
    """根据文件 ID 解析文件文本内容。"""
    result = await file_service.parse_file(db, request.file_id, request.parse_mode, request.force)
    return Result.success(result)


@router.post("/delete", response_model=Result[FileDeleteResponse], summary="删除文件")
def delete_files(request: FileDeleteRequest, db: Session = Depends(get_postgres_engine)):
    """删除文件记录和磁盘文件。"""
    result = file_service.delete_files(db, request.file_ids)
    return Result.success(result)
