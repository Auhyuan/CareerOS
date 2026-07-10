import asyncio
from pathlib import Path


class FileParser:
    """文件解析器，负责把上传文件转换成 Agent 可读取的文本。"""

    TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}

    async def parse_to_text(self, file_path: str, extension: str) -> str:
        """根据文件扩展名解析文本内容。

        Args:
            file_path: 文件真实存储路径。
            extension: 文件扩展名，包含或不包含点都可以。

        Returns:
            解析后的文本内容。

        Raises:
            RuntimeError: 文件不存在、格式不支持或解析失败时抛出。
        """
        path = Path(file_path)
        if not path.exists():
            raise RuntimeError(f"文件不存在: {file_path}")

        normalized_ext = self._normalize_extension(extension or path.suffix)
        if normalized_ext in self.TEXT_EXTENSIONS:
            return await asyncio.to_thread(self._read_text_file, path)
        if normalized_ext == ".pdf":
            return await asyncio.to_thread(self._parse_pdf_file, path)

        raise RuntimeError(f"暂不支持解析该文件类型: {normalized_ext or 'unknown'}")

    def _normalize_extension(self, extension: str) -> str:
        """标准化文件扩展名。"""
        cleaned = (extension or "").strip().lower()
        if not cleaned:
            return ""
        return cleaned if cleaned.startswith(".") else f".{cleaned}"

    def _read_text_file(self, path: Path) -> str:
        """读取文本类文件，兼容常见编码。"""
        for encoding in ("utf-8", "utf-8-sig", "gbk"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="ignore")

    def _parse_pdf_file(self, path: Path) -> str:
        """解析 PDF 文件。

        pypdf 作为可选依赖：未安装时给出明确提示，不影响服务启动。
        """
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise RuntimeError("缺少 PDF 解析依赖 pypdf，请先安装 pypdf 后再解析 PDF。") from error

        reader = PdfReader(str(path))
        parts: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                parts.append(f"[第 {index} 页]\n{text.strip()}")
        return "\n\n".join(parts)
