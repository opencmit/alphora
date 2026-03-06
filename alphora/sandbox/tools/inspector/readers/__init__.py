"""
Reader 注册表 + FileContent 统一接口

所有格式的 Reader 最终输出 FileContent，上层操作（view / search / outline / diff）
只依赖该结构，与具体文件格式解耦。
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class FileContent:
    """Reader 统一输出"""
    text: str
    total_lines: int
    file_type: str
    size: int
    metadata: dict = field(default_factory=dict)


_BINARY_EXTENSIONS = {".xlsx", ".xls", ".pdf", ".pptx"}

_EXCEL_EXTENSIONS = {".xlsx", ".xls", ".csv"}
_PDF_EXTENSIONS = {".pdf"}
_PPT_EXTENSIONS = {".pptx"}

_FILE_TYPE_MAP = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".jsx": "jsx", ".tsx": "tsx",
    ".json": "json", ".jsonl": "jsonl",
    ".md": "markdown", ".rst": "restructuredtext",
    ".txt": "text", ".log": "text",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "scss", ".less": "less",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".r": "r",
    ".java": "java", ".kt": "kotlin", ".scala": "scala",
    ".c": "c", ".cpp": "cpp", ".h": "c-header", ".hpp": "cpp-header",
    ".cs": "csharp", ".swift": "swift",
    ".xml": "xml", ".svg": "svg",
    ".ini": "ini", ".cfg": "ini", ".conf": "config",
    ".env": "env", ".dockerfile": "dockerfile",
    ".csv": "csv",
    ".xlsx": "excel", ".xls": "excel",
    ".pdf": "pdf",
    ".pptx": "pptx",
}


def humanize_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def get_file_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _FILE_TYPE_MAP.get(ext, ext.lstrip(".") or "unknown")


def is_binary_format(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in _BINARY_EXTENSIONS


def get_reader_info(path: str) -> tuple[str, bool]:
    """
    Returns (reader_type, needs_binary_read).

    reader_type: 'text' | 'excel' | 'pdf' | 'ppt'
    needs_binary_read: True if the sandbox should use read_file_bytes()
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return "excel", True
    if ext == ".csv":
        return "excel", False
    if ext in _PDF_EXTENSIONS:
        return "pdf", True
    if ext in _PPT_EXTENSIONS:
        return "ppt", True
    return "text", False


def read_file(
        data: Union[str, bytes],
        path: str,
        size: int,
        *,
        sheet: Optional[str] = None,
        page: Optional[int] = None,
) -> FileContent:
    """
    统一入口：根据文件扩展名分发到对应 Reader。

    Args:
        data: 文件内容（str 用于文本，bytes 用于二进制格式）
        path: 文件路径（用于检测扩展名）
        size: 原始文件大小
        sheet: Excel sheet 名（仅 excel reader 使用）
        page: 页码（仅 pdf / ppt reader 使用，1-indexed）
    """
    reader_type, _ = get_reader_info(path)

    if reader_type == "excel":
        from .excel import read
        return read(data, path, size, sheet=sheet)
    elif reader_type == "pdf":
        from .pdf import read
        return read(data, path, size, page=page)
    elif reader_type == "ppt":
        from .ppt import read
        return read(data, path, size, page=page)
    else:
        from .text import read
        return read(data, path, size)
