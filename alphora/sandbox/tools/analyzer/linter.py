"""
Lint 检查

策略: ruff 优先（Docker 镜像预装），不可用时 AST fallback。
"""

import ast
import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alphora.sandbox.sandbox import Sandbox


async def run_lint(
        sandbox: "Sandbox",
        path: str,
        max_issues: int = 50,
        severity: str = "all",
        fix: bool = False,
) -> dict:
    """
    对文件或目录执行 lint 检查。

    Returns:
        {
            "tool": str,
            "issues": [{"line", "column", "code", "message", "severity"}],
            "error_count": int,
            "warning_count": int,
            "info_count": int,
            "truncated": bool,
            "fixed": int,         # fix=True 时
        }
    """
    if await _tool_available(sandbox, "ruff"):
        return await _run_ruff(sandbox, path, max_issues, severity, fix)
    return await _run_ast_fallback(sandbox, path, max_issues, severity)


async def _tool_available(sandbox: "Sandbox", tool: str) -> bool:
    try:
        result = await sandbox.execute_shell(f"which {tool}", timeout=5)
        return result.success and result.stdout.strip() != ""
    except Exception:
        return False


# ── ruff ──

_RUFF_ERROR_PREFIXES = {"E", "F", "W"}

_SEVERITY_MAP = {
    "F": "error",    # pyflakes (fatal-level)
    "E": "error",    # pycodestyle errors
    "W": "warning",  # pycodestyle warnings
    "C": "warning",  # conventions
    "I": "info",     # isort
    "N": "info",     # naming
    "D": "info",     # docstring
    "S": "warning",  # bandit/security
    "B": "warning",  # bugbear
}


def _ruff_severity(code: str) -> str:
    if code:
        return _SEVERITY_MAP.get(code[0], "warning")
    return "warning"


async def _run_ruff(sandbox, path, max_issues, severity, fix) -> dict:
    if fix:
        await sandbox.execute_shell(f"ruff check --fix --quiet {path}", timeout=30)

    cmd = f"ruff check --output-format=json --quiet {path}"
    result = await sandbox.execute_shell(cmd, timeout=30)

    raw = result.stdout.strip()
    if not raw:
        return _empty_result("ruff", fix=fix)

    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        return _parse_ruff_text(result.stdout, max_issues, severity)

    issues = []
    for e in entries:
        sev = _ruff_severity(e.get("code", ""))
        if severity != "all" and sev != severity:
            continue
        issues.append({
            "line": e.get("location", {}).get("row", 0),
            "column": e.get("location", {}).get("column", 0),
            "code": e.get("code", ""),
            "message": e.get("message", ""),
            "severity": sev,
        })

    truncated = len(issues) > max_issues
    issues = issues[:max_issues]

    return _build_result("ruff", issues, truncated, fix=fix)


def _parse_ruff_text(text: str, max_issues: int, severity: str) -> dict:
    """Fallback: 解析 ruff 的文本输出格式"""
    pattern = re.compile(r"^(.+?):(\d+):(\d+):\s+(\w+)\s+(.+)$", re.MULTILINE)
    issues = []
    for m in pattern.finditer(text):
        code = m.group(4)
        sev = _ruff_severity(code)
        if severity != "all" and sev != severity:
            continue
        issues.append({
            "line": int(m.group(2)),
            "column": int(m.group(3)),
            "code": code,
            "message": m.group(5).strip(),
            "severity": sev,
        })
    truncated = len(issues) > max_issues
    return _build_result("ruff", issues[:max_issues], truncated)


# ── AST fallback ──

_AST_CHECKS = [
    ("mutable_default", "Mutable default argument"),
    ("bare_except", "Bare except clause"),
    ("empty_fstring", "f-string without placeholders"),
    ("duplicate_import", "Duplicate import"),
]


async def _run_ast_fallback(sandbox, path, max_issues, severity) -> dict:
    try:
        content = await sandbox.read_file(path)
    except Exception as e:
        return {"tool": "ast", "issues": [], "error": str(e),
                "error_count": 0, "warning_count": 0, "info_count": 0, "truncated": False}

    issues = []

    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as e:
        issues.append({
            "line": e.lineno or 0,
            "column": e.offset or 0,
            "code": "SyntaxError",
            "message": str(e.msg),
            "severity": "error",
        })
        return _build_result("ast", issues, False)

    issues.extend(_check_mutable_defaults(tree))
    issues.extend(_check_bare_except(tree))
    issues.extend(_check_duplicate_imports(tree))
    issues.extend(_check_empty_fstrings(tree))

    if severity != "all":
        issues = [i for i in issues if i["severity"] == severity]

    truncated = len(issues) > max_issues
    return _build_result("ast", issues[:max_issues], truncated)


def _check_mutable_defaults(tree: ast.AST) -> list:
    issues = []
    mutable_types = (ast.List, ast.Dict, ast.Set, ast.Call)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if default and isinstance(default, mutable_types):
                    issues.append({
                        "line": default.lineno,
                        "column": default.col_offset + 1,
                        "code": "B006",
                        "message": f"Mutable default argument in '{node.name}'",
                        "severity": "warning",
                    })
    return issues


def _check_bare_except(tree: ast.AST) -> list:
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append({
                "line": node.lineno,
                "column": node.col_offset + 1,
                "code": "E722",
                "message": "Bare 'except:' clause (use 'except Exception:' instead)",
                "severity": "warning",
            })
    return issues


def _check_duplicate_imports(tree: ast.AST) -> list:
    issues = []
    seen = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name in seen:
                    issues.append({
                        "line": node.lineno,
                        "column": node.col_offset + 1,
                        "code": "F811",
                        "message": f"Duplicate import '{name}' (first at line {seen[name]})",
                        "severity": "warning",
                    })
                else:
                    seen[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                key = f"{module}.{alias.name}"
                if key in seen:
                    issues.append({
                        "line": node.lineno,
                        "column": node.col_offset + 1,
                        "code": "F811",
                        "message": f"Duplicate import '{alias.name}' from '{module}' (first at line {seen[key]})",
                        "severity": "warning",
                    })
                else:
                    seen[key] = node.lineno
    return issues


def _check_empty_fstrings(tree: ast.AST) -> list:
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr) and not any(
            isinstance(v, ast.FormattedValue) for v in node.values
        ):
            issues.append({
                "line": node.lineno,
                "column": node.col_offset + 1,
                "code": "F541",
                "message": "f-string without any placeholders",
                "severity": "warning",
            })
    return issues


# ── helpers ──

def _empty_result(tool: str, **extra) -> dict:
    return {
        "tool": tool,
        "issues": [],
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "truncated": False,
        **extra,
    }


def _build_result(tool: str, issues: list, truncated: bool, **extra) -> dict:
    return {
        "tool": tool,
        "issues": issues,
        "error_count": sum(1 for i in issues if i["severity"] == "error"),
        "warning_count": sum(1 for i in issues if i["severity"] == "warning"),
        "info_count": sum(1 for i in issues if i["severity"] == "info"),
        "truncated": truncated,
        **extra,
    }
