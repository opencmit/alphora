"""
文件搜索引擎

- search_content: 单文件内搜索（纯逻辑，无 I/O）
- search_directory: 跨目录递归搜索（异步，需 Sandbox 实例）
"""

import re
import fnmatch
from typing import Optional, TYPE_CHECKING

from alphora.sandbox.tools.inspector.readers import FileContent, get_reader_info, read_file

if TYPE_CHECKING:
    from alphora.sandbox.sandbox import Sandbox


def search_content(
        file_content: FileContent,
        pattern: str,
        regex: bool = False,
        context_lines: int = 3,
        max_matches: int = 20,
) -> dict:
    """
    在单个文件内容中搜索。

    Returns:
        {
            "matches": [{"line": int, "column": int, "text": str, "context": str}],
            "match_count": int,          # 实际总匹配数
            "shown_matches": int,        # 返回的匹配数（受 max_matches 限制）
            "matches_truncated": bool,
        }
    """
    lines = file_content.text.splitlines()
    total = len(lines)
    width = len(str(total))

    if regex:
        try:
            compiled = re.compile(pattern)
        except re.error as e:
            return {
                "matches": [],
                "match_count": 0,
                "shown_matches": 0,
                "matches_truncated": False,
                "error": f"Invalid regex: {e}",
            }
        match_func = compiled.search
    else:
        match_func = lambda line: _simple_find(line, pattern)

    all_match_indices = []
    for i, line in enumerate(lines):
        if match_func(line):
            all_match_indices.append(i)

    total_match_count = len(all_match_indices)
    display_indices = all_match_indices[:max_matches]

    matches = []
    for idx in display_indices:
        line = lines[idx]
        line_num = idx + 1

        if regex:
            m = compiled.search(line)
            col = m.start() + 1 if m else 1
        else:
            pos = line.find(pattern)
            col = pos + 1 if pos >= 0 else 1

        ctx_start = max(0, idx - context_lines)
        ctx_end = min(total, idx + context_lines + 1)
        ctx_lines = []
        for j in range(ctx_start, ctx_end):
            prefix = ">" if j == idx else " "
            ctx_lines.append(f"{prefix}{j + 1:>{width}}|{lines[j]}")

        matches.append({
            "line": line_num,
            "column": col,
            "text": line,
            "context": "\n".join(ctx_lines),
        })

    return {
        "matches": matches,
        "match_count": total_match_count,
        "shown_matches": len(matches),
        "matches_truncated": total_match_count > max_matches,
    }


async def search_directory(
        sandbox: "Sandbox",
        dir_path: str,
        pattern: str,
        regex: bool = False,
        context_lines: int = 3,
        max_matches: int = 20,
        glob_pattern: Optional[str] = None,
        max_files: int = 10,
        encoding: str = "utf-8",
) -> dict:
    """
    跨目录递归搜索。

    Returns:
        {
            "file_matches": [{file, match_count, matches}],
            "total_match_count": int,
            "files_searched": int,
            "files_with_matches": int,
            "matches_truncated": bool,
        }
    """
    all_files = await sandbox.list_files(dir_path, recursive=True)

    candidates = []
    for f in all_files:
        if f.is_directory:
            continue
        if glob_pattern and not fnmatch.fnmatch(f.name, glob_pattern):
            continue
        reader_type, needs_binary = get_reader_info(f.path)
        if needs_binary:
            continue
        candidates.append(f)

    if len(candidates) > max_files:
        candidates = candidates[:max_files]
        files_truncated = True
    else:
        files_truncated = False

    file_matches = []
    total_match_count = 0
    remaining_matches = max_matches

    for f in candidates:
        if remaining_matches <= 0:
            break

        try:
            text = await sandbox.read_file(f.path)
        except Exception:
            continue

        fc = FileContent(
            text=text,
            total_lines=len(text.splitlines()),
            file_type="text",
            size=f.size,
        )

        result = search_content(
            fc, pattern,
            regex=regex,
            context_lines=context_lines,
            max_matches=remaining_matches,
        )

        if result["match_count"] > 0:
            total_match_count += result["match_count"]
            remaining_matches -= result["shown_matches"]
            file_matches.append({
                "file": f.path,
                "match_count": result["match_count"],
                "matches": result["matches"],
            })

    return {
        "file_matches": file_matches,
        "total_match_count": total_match_count,
        "files_searched": len(candidates),
        "files_with_matches": len(file_matches),
        "matches_truncated": total_match_count > max_matches or files_truncated,
    }


class _SimpleMatch:
    """模拟 re.Match 接口，用于统一 match_func 返回值"""
    __slots__ = ("_start",)

    def __init__(self, start: int):
        self._start = start

    def start(self):
        return self._start

    def __bool__(self):
        return True


def _simple_find(line: str, pattern: str):
    pos = line.find(pattern)
    return _SimpleMatch(pos) if pos >= 0 else None
