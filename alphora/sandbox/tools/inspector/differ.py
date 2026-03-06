"""
文件对比器

生成两个文件之间的 unified diff 和变更统计。
"""

import difflib

from alphora.sandbox.tools.inspector.readers import FileContent


def diff_contents(
        content_a: FileContent,
        content_b: FileContent,
        path_a: str,
        path_b: str,
        context_lines: int = 3,
) -> dict:
    """
    计算两个文件的 unified diff。

    Returns:
        {
            "diff": str,
            "has_changes": bool,
            "stats": {"added": int, "removed": int, "changed_regions": int},
        }
    """
    lines_a = content_a.text.splitlines(keepends=True)
    lines_b = content_b.text.splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(
        lines_a, lines_b,
        fromfile=f"a/{path_a}",
        tofile=f"b/{path_b}",
        n=context_lines,
    ))

    diff_text = "".join(diff_lines)

    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
    regions = sum(1 for l in diff_lines if l.startswith("@@"))

    return {
        "diff": diff_text,
        "has_changes": bool(diff_lines),
        "stats": {
            "added": added,
            "removed": removed,
            "changed_regions": regions,
        },
    }
