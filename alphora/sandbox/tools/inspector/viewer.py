"""
文件内容查看器

负责行范围切片、行号格式化、智能截断。
所有输入为 FileContent，不涉及 I/O。
"""

from typing import Optional

from alphora.sandbox.tools.inspector.readers import FileContent


def view_content(
        file_content: FileContent,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        max_lines: int = 100,
        line_numbers: bool = False,
) -> dict:
    """
    从 FileContent 中切片并格式化输出。

    Args:
        file_content: Reader 产出的统一文件内容
        start_line: 起始行（1-indexed），负数表示倒数
        end_line: 结束行（1-indexed），负数表示倒数
        max_lines: 单次最大返回行数
        line_numbers: 是否带行号

    Returns:
        {"content": str, "shown_range": [start, end], "truncated": bool}
    """
    lines = file_content.text.splitlines()
    total = len(lines)

    if total == 0:
        return {"content": "", "shown_range": [0, 0], "truncated": False}

    # Resolve negative indices
    start = _resolve_line(start_line, total) if start_line is not None else 1
    start = max(1, min(start, total))

    if end_line is not None:
        end = _resolve_line(end_line, total)
        end = max(start, min(end, total))
    else:
        end = min(start + max_lines - 1, total)

    # Enforce max_lines
    if end - start + 1 > max_lines:
        end = start + max_lines - 1

    truncated = end < total

    width = len(str(total))
    output = []
    for i in range(start - 1, end):
        line = lines[i]
        if line_numbers:
            output.append(f"{i + 1:>{width}}|{line}")
        else:
            output.append(line)

    return {
        "content": "\n".join(output),
        "shown_range": [start, end],
        "truncated": truncated,
    }


def _resolve_line(n: int, total: int) -> int:
    """将负数行号转为正数（-1 = 最后一行）"""
    if n < 0:
        return max(1, total + n + 1)
    return n
