"""
Code Analyzer — 沙箱代码 Lint 检查工具

单入口 code_analyzer()，ruff 优先，不可用时 AST fallback。
"""

from typing import TYPE_CHECKING

from alphora.sandbox.tools.analyzer.linter import run_lint

if TYPE_CHECKING:
    from alphora.sandbox.sandbox import Sandbox

__all__ = ["code_analyzer"]


async def code_analyzer(
        sandbox: "Sandbox",
        path: str,
        fix: bool = False,
        max_issues: int = 50,
        severity: str = "all",
) -> dict:
    """
    对沙箱内的 Python 文件或目录执行 lint 检查。

    使用 ruff（Docker 镜像预装），不可用时自动切换到 AST fallback。

    Args:
        sandbox:    Sandbox 实例
        path:       文件或目录路径（沙箱内）
        fix:        自动修复 lint 问题（仅 ruff 支持）
        max_issues: 最大返回问题数（默认 50）
        severity:   过滤级别 ("all" | "error" | "warning")

    Returns:
        {
            "success": bool,
            "tool": str,
            "issues": [{"line", "column", "code", "message", "severity"}],
            "error_count": int,
            "warning_count": int,
            "info_count": int,
            "truncated": bool,
            "error": str,
        }
    """
    if not await _path_exists(sandbox, path):
        return {
            "success": False,
            "error": f"Path not found: {path}",
        }

    try:
        result = await run_lint(
            sandbox, path,
            max_issues=max_issues,
            severity=severity,
            fix=fix,
        )
        return {"success": True, "error": "", **result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _path_exists(sandbox: "Sandbox", path: str) -> bool:
    if await sandbox.file_exists(path):
        return True
    try:
        await sandbox.list_files(path)
        return True
    except Exception:
        return False
