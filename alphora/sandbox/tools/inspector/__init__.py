"""
File Inspector — LLM 友好的沙箱文件检查工具

单入口 file_inspector() 覆盖：查看、搜索、大纲、对比、元信息，
自动区分文件 / 目录并做合法性校验。
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING

from alphora.sandbox.tools.inspector.readers import (
    FileContent,
    humanize_size,
    get_file_type,
    get_reader_info,
    is_binary_format,
    read_file,
)
from alphora.sandbox.tools.inspector.viewer import view_content
from alphora.sandbox.tools.inspector.searcher import search_content, search_directory
from alphora.sandbox.tools.inspector.outliner import extract_outline
from alphora.sandbox.tools.inspector.differ import diff_contents

if TYPE_CHECKING:
    from alphora.sandbox.sandbox import Sandbox

__all__ = ["file_inspector"]


# ── helpers ──

def _success(data: dict) -> dict:
    return {"success": True, "error": "", **data}


def _error(code: str, message: str, **extra) -> dict:
    return {"success": False, "error": code, "message": message, **extra}


async def _check_path_type(sandbox: "Sandbox", path: str) -> str:
    """Returns 'file', 'directory', or raises."""
    if await sandbox.file_exists(path):
        return "file"
    try:
        await sandbox.list_files(path)
        return "directory"
    except Exception:
        pass
    return "not_found"


async def _read_file_content(
        sandbox: "Sandbox",
        path: str,
        encoding: str = "utf-8",
        sheet: Optional[str] = None,
        page: Optional[int] = None,
) -> FileContent:
    """通过 Sandbox 读取文件并交给对应 Reader 解析。"""
    _, needs_binary = get_reader_info(path)

    if needs_binary:
        data = await sandbox.read_file_bytes(path)
        size = len(data)
    else:
        data = await sandbox.read_file(path)
        size = len(data.encode(encoding))

    return read_file(data, path, size, sheet=sheet, page=page)


def _build_file_info(file_content: FileContent, path: str, encoding: str = "utf-8") -> dict:
    return {
        "path": path,
        "size": file_content.size,
        "size_human": humanize_size(file_content.size),
        "total_lines": file_content.total_lines,
        "type": file_content.file_type,
        "encoding": encoding,
        "metadata": file_content.metadata,
    }


async def _build_dir_info(sandbox: "Sandbox", path: str) -> dict:
    files = await sandbox.list_files(path, recursive=True)

    total_size = 0
    type_counts: Dict[str, int] = {}
    file_count = 0

    for f in files:
        if f.is_directory:
            continue
        file_count += 1
        total_size += f.size or 0
        ft = get_file_type(f.name)
        type_counts[ft] = type_counts.get(ft, 0) + 1

    return {
        "path": path,
        "total_files": file_count,
        "total_size": total_size,
        "total_size_human": humanize_size(total_size),
        "file_types": type_counts,
    }


_DIR_ONLY_OPS = {"search", "info_only"}


# ── main entry ──

async def file_inspector(
        sandbox: "Sandbox",
        path: str,
        # mode switches (priority: info_only > diff_with > outline > search > view)
        search: Optional[str] = None,
        outline: bool = False,
        info_only: bool = False,
        diff_with: Optional[str] = None,
        # view control
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        max_lines: int = 100,
        # search control
        regex: bool = False,
        context_lines: int = 3,
        max_matches: int = 20,
        glob_pattern: Optional[str] = None,
        max_files: int = 10,
        # diff control
        diff_context_lines: int = 3,
        # format control
        line_numbers: bool = False,
        encoding: str = "utf-8",
        # format-specific
        sheet: Optional[str] = None,
        page: Optional[int] = None,
) -> dict:
    """
    LLM 友好的沙箱文件检查工具。

    通过一个入口覆盖查看、搜索、大纲、对比、元信息等操作。
    自动区分文件 / 目录，对不支持的组合给出清晰报错。

    Args:
        sandbox:          Sandbox 实例
        path:             文件路径 或 目录路径（沙箱内）
        search:           搜索模式：搜索该字符串/正则
        outline:          大纲模式：提取 class/def/function 结构签名
        info_only:        元信息模式：只返回大小、行数等
        diff_with:        对比模式：与另一个文件做 unified diff
        start_line:       起始行（1-indexed），负数表示倒数
        end_line:         结束行（1-indexed），负数表示倒数
        max_lines:        单次最大返回行数
        regex:            search 是否为正则表达式
        context_lines:    搜索匹配结果前后上下文行数
        max_matches:      最大匹配数
        glob_pattern:     目录搜索时的文件名过滤（如 "*.py"）
        max_files:        目录搜索时最多搜索的文件数
        diff_context_lines: diff 输出上下文行数
        line_numbers:     是否带行号（默认关闭）
        encoding:         文件编码
        sheet:            Excel: 指定 sheet 名称
        page:             PDF/PPT: 指定页码（1-indexed）
    """
    # ── 1. path type check ──
    path_type = await _check_path_type(sandbox, path)

    if path_type == "not_found":
        return _error("PATH_NOT_FOUND", f"Path not found: {path}")

    # ── 2. directory handling ──
    if path_type == "directory":
        requested_ops = []
        if search:
            requested_ops.append("search")
        if outline:
            requested_ops.append("outline")
        if diff_with:
            requested_ops.append("diff_with")
        if not search and not info_only and not outline and not diff_with:
            requested_ops.append("view")

        unsupported = [op for op in requested_ops if op not in _DIR_ONLY_OPS]
        if unsupported:
            op_names = ", ".join(f"'{op}'" for op in unsupported)
            return _error(
                "DIRECTORY_NOT_SUPPORTED",
                f"{op_names} is not supported for directories. "
                f"Please specify a file path, e.g. '{path.rstrip('/')}/some_file.py'. "
                f"For directories, only 'search' and 'info_only' are available.",
            )

        if info_only:
            dir_info = await _build_dir_info(sandbox, path)
            return _success({"dir_info": dir_info})

        # directory + search
        result = await search_directory(
            sandbox, path, search,
            regex=regex,
            context_lines=context_lines,
            max_matches=max_matches,
            glob_pattern=glob_pattern,
            max_files=max_files,
            encoding=encoding,
        )
        dir_info = await _build_dir_info(sandbox, path)
        return _success({"dir_info": dir_info, **result})

    # ── 3. file handling ──
    try:
        # info_only: only metadata, skip reading content for binary heavy files
        if info_only:
            fc = await _read_file_content(sandbox, path, encoding, sheet=sheet, page=page)
            return _success({"file_info": _build_file_info(fc, path, encoding)})

        # diff mode
        if diff_with is not None:
            fc_a = await _read_file_content(sandbox, path, encoding, sheet=sheet, page=page)
            fc_b = await _read_file_content(sandbox, diff_with, encoding)
            diff_result = diff_contents(fc_a, fc_b, path, diff_with, context_lines=diff_context_lines)
            return _success({
                "file_info": _build_file_info(fc_a, path, encoding),
                **diff_result,
            })

        # read content
        fc = await _read_file_content(sandbox, path, encoding, sheet=sheet, page=page)
        file_info = _build_file_info(fc, path, encoding)

        # outline mode
        if outline:
            outline_result = extract_outline(fc)
            return _success({
                "file_info": file_info,
                **outline_result,
            })

        # search mode (single file)
        if search is not None:
            search_result = search_content(
                fc, search,
                regex=regex,
                context_lines=context_lines,
                max_matches=max_matches,
            )
            return _success({
                "file_info": file_info,
                **search_result,
            })

        # default: view mode
        view_result = view_content(
            fc,
            start_line=start_line,
            end_line=end_line,
            max_lines=max_lines,
            line_numbers=line_numbers,
        )
        return _success({
            "file_info": file_info,
            **view_result,
        })

    except Exception as e:
        return _error("INSPECT_FAILED", str(e))
