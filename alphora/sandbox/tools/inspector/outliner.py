"""
文件结构大纲提取器

从源代码中提取 class / function / import / 常量等结构签名，
让 LLM 快速了解文件骨架而无需阅读全部实现。

支持: Python, JavaScript/TypeScript, 通用缩进启发式
"""

import re

from alphora.sandbox.tools.inspector.readers import FileContent


def extract_outline(file_content: FileContent) -> dict:
    """
    提取文件结构大纲。

    Returns:
        {"content": str, "entry_count": int}
    """
    lang = file_content.file_type
    lines = file_content.text.splitlines()

    if lang == "python":
        entries = _python_outline(lines)
    elif lang in ("javascript", "typescript", "jsx", "tsx"):
        entries = _js_outline(lines)
    else:
        entries = _generic_outline(lines)

    if not entries:
        return {"content": "(no structural elements found)", "entry_count": 0}

    total = file_content.total_lines
    width = len(str(total))

    output_lines = []
    for line_num, text in entries:
        output_lines.append(f"{line_num:>{width}}  {text}")

    return {
        "content": "\n".join(output_lines),
        "entry_count": len(entries),
    }


# ── Python ──

_PY_PATTERNS = [
    re.compile(r"^(from\s+\S+\s+import\s+.+|import\s+.+)$"),
    re.compile(r"^[A-Z_][A-Z_0-9]*\s*="),
    re.compile(r"^class\s+\w+"),
    re.compile(r"^(?:async\s+)?def\s+\w+"),
    re.compile(r"^\s+(?:async\s+)?def\s+\w+"),
]


def _python_outline(lines: list[str]) -> list[tuple[int, str]]:
    entries = []
    prev_is_decorator = False
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if not stripped or stripped.startswith("#"):
            prev_is_decorator = False
            continue

        if stripped.lstrip().startswith("@"):
            prev_is_decorator = True
            continue

        for pat in _PY_PATTERNS:
            if pat.match(stripped):
                entries.append((i + 1, stripped))
                break

        prev_is_decorator = False
    return entries


# ── JavaScript / TypeScript ──

_JS_PATTERNS = [
    re.compile(r"^import\s+"),
    re.compile(r"^(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+\w+"),
    re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s+\w+"),
    re.compile(r"^\s+(?:async\s+)?(?:static\s+)?(?:get\s+|set\s+)?(?:#?\w+)\s*\("),
    re.compile(r"^(?:export\s+)?(?:const|let|var)\s+\w+"),
    re.compile(r"^(?:export\s+)?(?:type|interface|enum)\s+\w+"),
]


def _js_outline(lines: list[str]) -> list[tuple[int, str]]:
    entries = []
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if not stripped or stripped.startswith("//"):
            continue
        for pat in _JS_PATTERNS:
            if pat.match(stripped):
                display = stripped
                if len(display) > 120:
                    display = display[:117] + "..."
                entries.append((i + 1, display))
                break
    return entries


# ── Generic (indentation-based heuristic) ──

_GENERIC_PATTERNS = [
    re.compile(r"^(?:public|private|protected|static|abstract|async)?\s*(?:class|struct|enum|interface|trait)\s+\w+", re.IGNORECASE),
    re.compile(r"^(?:public|private|protected|static|abstract|async|virtual|override)?\s*(?:def|func|fn|fun|function|sub|proc|method)\s+\w+", re.IGNORECASE),
    re.compile(r"^\s{2,8}(?:public|private|protected|static|abstract|async|virtual|override)?\s*(?:def|func|fn|fun|function|sub|proc|method)\s+\w+", re.IGNORECASE),
    re.compile(r"^(?:import|from|require|include|use|using)\s+", re.IGNORECASE),
]


def _generic_outline(lines: list[str]) -> list[tuple[int, str]]:
    entries = []
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if not stripped:
            continue
        for pat in _GENERIC_PATTERNS:
            if pat.match(stripped):
                display = stripped
                if len(display) > 120:
                    display = display[:117] + "..."
                entries.append((i + 1, display))
                break
    return entries
