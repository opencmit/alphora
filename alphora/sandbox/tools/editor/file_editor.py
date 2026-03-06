"""
AI 文件增量编辑工具
采用"搜索替换为主，全量重写兜底"策略

提供两种运行模式：
- 本地模式：直接操作文件系统 (file_editor)
- 沙箱模式：通过 Sandbox 实例异步操作 (sandbox_file_editor)

核心编辑逻辑 (apply_edits_to_content) 与 I/O 完全解耦，两种模式共享。
"""

import os
import shutil
import difflib
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from alphora.sandbox.sandbox import Sandbox


class MatchMethod(Enum):
    EXACT = "exact"
    WHITESPACE_NORMALIZED = "whitespace_normalized"
    FUZZY = "fuzzy"


class MatchStrategy(Enum):
    EXACT = "exact"
    FUZZY = "fuzzy"


@dataclass
class EditBlock:
    """单个搜索替换块"""
    search: str
    replace: str


@dataclass
class EditBlockResult:
    """单个编辑块的应用结果"""
    index: int
    status: str  # "applied" | "failed"
    match_method: Optional[str] = None
    match_line: Optional[int] = None  # 1-indexed
    error: Optional[str] = None


@dataclass
class EditResult:
    """编辑总结果"""
    success: bool
    mode: str
    file_path: str
    backup_path: Optional[str] = None
    edit_results: list[EditBlockResult] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    diff: str = ""
    error: Optional[str] = None
    message: Optional[str] = None


# ============================================================================
# Pure matching / diffing helpers (no I/O)
# ============================================================================

def _find_exact(content: str, search: str) -> list[int]:
    """精确匹配，返回所有匹配的起始位置"""
    positions = []
    start = 0
    while True:
        pos = content.find(search, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1
    return positions


def _normalize_whitespace(text: str) -> str:
    """每行去除前导空白，用于宽松匹配"""
    return "\n".join(line.lstrip() for line in text.splitlines())


def _find_whitespace_normalized(content: str, search: str) -> list[int]:
    """
    忽略前导空白的匹配。
    返回原始 content 中匹配段的起始位置列表。
    """
    norm_content = _normalize_whitespace(content)
    norm_search = _normalize_whitespace(search)

    positions = []
    start = 0
    while True:
        pos = norm_content.find(norm_search, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1

    if not positions:
        return []

    orig_lines = content.splitlines()
    search_line_count = len(search.splitlines())

    result_positions = []
    for pos in positions:
        line_idx = norm_content[:pos].count("\n")
        char_pos = sum(len(orig_lines[i]) + 1 for i in range(line_idx))
        end_line_idx = line_idx + search_line_count
        if end_line_idx <= len(orig_lines):
            result_positions.append(char_pos)

    return result_positions


def _find_fuzzy(content: str, search: str, threshold: float = 0.8) -> tuple[Optional[int], float]:
    """
    相似度匹配。在 content 中滑动窗口找与 search 最相似的片段。
    返回 (最佳匹配的起始位置, 相似度)，未达阈值返回 (None, best_ratio)。
    """
    search_lines = search.splitlines()
    content_lines = content.splitlines()
    window = len(search_lines)

    if window == 0 or len(content_lines) == 0:
        return None, 0.0

    best_ratio = 0.0
    best_line_idx = 0

    for i in range(len(content_lines) - window + 1):
        candidate = "\n".join(content_lines[i:i + window])
        ratio = difflib.SequenceMatcher(None, search, candidate).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_line_idx = i

    if best_ratio >= threshold:
        char_pos = sum(len(content_lines[i]) + 1 for i in range(best_line_idx))
        return char_pos, best_ratio

    return None, best_ratio


def _get_match_span(content: str, pos: int, search: str, match_method: MatchMethod) -> tuple[int, int]:
    """根据匹配方式，返回原始内容中应被替换的 (start, end) 字符范围"""
    if match_method == MatchMethod.EXACT:
        return pos, pos + len(search)

    search_line_count = len(search.splitlines())
    content_lines = content.splitlines(keepends=True)
    line_idx = content[:pos].count("\n")
    start = pos
    end = start
    for i in range(search_line_count):
        if line_idx + i < len(content_lines):
            end += len(content_lines[line_idx + i])
    return start, end


def _ensure_trailing_newline(matched_text: str, replacement: str) -> str:
    """如果被匹配的原文以换行结尾，而替换内容没有，则补一个换行"""
    if matched_text.endswith("\n") and not replacement.endswith("\n"):
        return replacement + "\n"
    return replacement


def _compute_diff(original: str, modified: str, file_path: str) -> str:
    """计算 unified diff"""
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines, mod_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    return "".join(diff)


def _compute_stats(original: str, modified: str) -> dict:
    """计算变更统计"""
    orig_lines = original.splitlines()
    mod_lines = modified.splitlines()
    diff = list(difflib.unified_diff(orig_lines, mod_lines, n=0))

    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    regions = sum(1 for line in diff if line.startswith("@@"))

    return {
        "total_lines": len(mod_lines),
        "added_lines": added,
        "removed_lines": removed,
        "changed_regions": regions,
    }


def _atomic_write(file_path: str, content: str) -> None:
    """原子写入：先写临时文件，再 rename"""
    dir_name = os.path.dirname(os.path.abspath(file_path))
    with tempfile.NamedTemporaryFile(mode="w", dir=dir_name, delete=False, suffix=".tmp") as f:
        f.write(content)
        tmp_path = f.name
    shutil.move(tmp_path, file_path)


# ============================================================================
# Core editing logic (pure, no I/O)
# ============================================================================

def apply_edits_to_content(
        original_content: str,
        edits: list[dict],
        match_strategy: str = "fuzzy",
        fuzzy_threshold: float = 0.8,
) -> tuple[str, list[EditBlockResult], bool]:
    """
    对内容字符串应用搜索替换编辑块。纯逻辑，不涉及任何 I/O。

    Args:
        original_content: 原始文本
        edits: 编辑块列表，每个元素 {"search": str, "replace": str}
        match_strategy: "exact" | "fuzzy"
        fuzzy_threshold: 相似度匹配阈值 (0~1)

    Returns:
        (modified_content, block_results, all_success) 三元组
    """
    content = original_content
    edit_blocks = [EditBlock(**e) for e in edits]
    block_results: list[EditBlockResult] = []
    all_success = True

    for idx in range(len(edit_blocks) - 1, -1, -1):
        block = edit_blocks[idx]

        positions = _find_exact(content, block.search)

        if len(positions) == 1:
            start, end = _get_match_span(content, positions[0], block.search, MatchMethod.EXACT)
            content = content[:start] + block.replace + content[end:]
            line_num = content[:start].count("\n") + 1
            block_results.append(EditBlockResult(
                index=idx, status="applied",
                match_method=MatchMethod.EXACT.value, match_line=line_num,
            ))
            continue

        if len(positions) > 1:
            all_success = False
            block_results.append(EditBlockResult(
                index=idx, status="failed",
                error=f"Ambiguous match: found {len(positions)} occurrences."
            ))
            continue

        if match_strategy == "exact":
            all_success = False
            block_results.append(EditBlockResult(
                index=idx, status="failed",
                error="No exact match found."
            ))
            continue

        ws_positions = _find_whitespace_normalized(content, block.search)

        if len(ws_positions) == 1:
            start, end = _get_match_span(content, ws_positions[0], block.search, MatchMethod.WHITESPACE_NORMALIZED)
            replacement = _ensure_trailing_newline(content[start:end], block.replace)
            content = content[:start] + replacement + content[end:]
            line_num = content[:start].count("\n") + 1
            block_results.append(EditBlockResult(
                index=idx, status="applied",
                match_method=MatchMethod.WHITESPACE_NORMALIZED.value, match_line=line_num,
            ))
            continue

        if len(ws_positions) > 1:
            all_success = False
            block_results.append(EditBlockResult(
                index=idx, status="failed",
                error=f"Ambiguous whitespace-normalized match: found {len(ws_positions)} occurrences."
            ))
            continue

        fuzzy_pos, ratio = _find_fuzzy(content, block.search, threshold=fuzzy_threshold)

        if fuzzy_pos is not None:
            start, end = _get_match_span(content, fuzzy_pos, block.search, MatchMethod.FUZZY)
            replacement = _ensure_trailing_newline(content[start:end], block.replace)
            content = content[:start] + replacement + content[end:]
            line_num = content[:start].count("\n") + 1
            block_results.append(EditBlockResult(
                index=idx, status="applied",
                match_method=MatchMethod.FUZZY.value, match_line=line_num,
            ))
            continue

        all_success = False
        block_results.append(EditBlockResult(
            index=idx, status="failed",
            error=f"No match found (best similarity: {ratio:.2f}, threshold: {fuzzy_threshold:.2f})"
        ))

    block_results.sort(key=lambda r: r.index)
    return content, block_results, all_success


def file_editor(
        file_path: str,
        mode: str = "search_replace",
        edits: Optional[list[dict]] = None,
        new_content: Optional[str] = None,
        backup: bool = True,
        match_strategy: str = "fuzzy",
        fuzzy_threshold: float = 0.8,
) -> dict:
    """
    AI 文件增量编辑函数（本地文件系统版本）。

    Args:
        file_path:        目标文件路径
        mode:             "search_replace" | "full_rewrite"
        edits:            search_replace 模式的编辑块列表，每个元素为 {"search": str, "replace": str}
        new_content:      full_rewrite 模式的完整新文件内容
        backup:           是否在修改前备份原文件为 .bak
        match_strategy:   "exact" | "fuzzy"（fuzzy 会依次尝试精确→去空白→相似度匹配）
        fuzzy_threshold:  相似度匹配的阈值，默认 0.8

    Returns:
        dict: 包含 success, mode, file_path, backup_path, edit_results, stats, diff, error, message
    """

    if mode not in ("search_replace", "full_rewrite"):
        return EditResult(
            success=False, mode=mode, file_path=file_path,
            error="INVALID_INPUT", message=f"Invalid mode: {mode}. Use 'search_replace' or 'full_rewrite'."
        ).__dict__

    if not os.path.isfile(file_path):
        return EditResult(
            success=False, mode=mode, file_path=file_path,
            error="FILE_NOT_FOUND", message=f"File not found: {file_path}"
        ).__dict__

    if mode == "search_replace" and (not edits or not isinstance(edits, list)):
        return EditResult(
            success=False, mode=mode, file_path=file_path,
            error="INVALID_INPUT", message="search_replace mode requires a non-empty 'edits' list."
        ).__dict__

    if mode == "full_rewrite" and new_content is None:
        return EditResult(
            success=False, mode=mode, file_path=file_path,
            error="INVALID_INPUT", message="full_rewrite mode requires 'new_content'."
        ).__dict__

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()
    except Exception as e:
        return EditResult(
            success=False, mode=mode, file_path=file_path,
            error="WRITE_FAILED", message=f"Failed to read file: {e}"
        ).__dict__

    backup_path = None
    if backup:
        backup_path = file_path + ".bak"
        try:
            shutil.copy2(file_path, backup_path)
        except Exception as e:
            return EditResult(
                success=False, mode=mode, file_path=file_path,
                error="WRITE_FAILED", message=f"Failed to create backup: {e}"
            ).__dict__

    if mode == "full_rewrite":
        modified_content = new_content
        diff_text = _compute_diff(original_content, modified_content, file_path)
        stats = _compute_stats(original_content, modified_content)

        try:
            _atomic_write(file_path, modified_content)
        except Exception as e:
            return EditResult(
                success=False, mode=mode, file_path=file_path, backup_path=backup_path,
                error="WRITE_FAILED", message=f"Failed to write file: {e}"
            ).__dict__

        return EditResult(
            success=True, mode=mode, file_path=file_path, backup_path=backup_path,
            stats=stats, diff=diff_text,
        ).__dict__

    # search_replace via shared core logic
    content, block_results, all_success = apply_edits_to_content(
        original_content, edits, match_strategy, fuzzy_threshold,
    )

    diff_text = _compute_diff(original_content, content, file_path)
    stats = _compute_stats(original_content, content)

    if content != original_content:
        try:
            _atomic_write(file_path, content)
        except Exception as e:
            return EditResult(
                success=False, mode=mode, file_path=file_path, backup_path=backup_path,
                edit_results=[r.__dict__ for r in block_results],
                error="WRITE_FAILED", message=f"Failed to write file: {e}"
            ).__dict__

    result = EditResult(
        success=all_success,
        mode=mode,
        file_path=file_path,
        backup_path=backup_path,
        edit_results=[r.__dict__ for r in block_results],
        stats=stats,
        diff=diff_text,
    )

    if not all_success:
        failed = [r for r in block_results if r.status == "failed"]
        result.error = "MATCH_NOT_FOUND"
        result.message = f"{len(failed)} of {len(edits)} edit(s) failed to apply."

    return result.__dict__


async def sandbox_file_editor(
        sandbox: "Sandbox",
        file_path: str,
        mode: str = "search_replace",
        edits: Optional[list[dict]] = None,
        new_content: Optional[str] = None,
        backup: bool = True,
        match_strategy: str = "fuzzy",
        fuzzy_threshold: float = 0.8,
) -> dict:
    """
    AI 文件增量编辑函数（沙箱异步版本）

    通过 Sandbox 实例进行文件读写，适用于 local / docker 等各种后端。
    编辑逻辑与本地版完全一致，共享 apply_edits_to_content 核心。

    Args:
        sandbox:          Sandbox 实例（须已 start）
        file_path:        目标文件路径（沙箱内路径）
        mode:             "search_replace" | "full_rewrite"
        edits:            search_replace 模式的编辑块列表
        new_content:      full_rewrite 模式的完整新文件内容
        backup:           是否在修改前备份
        match_strategy:   "exact" | "fuzzy"
        fuzzy_threshold:  相似度匹配的阈值

    Returns:
        dict: 包含 success, mode, file_path, backup_path, edit_results, stats, diff, error, message
    """
    if mode not in ("search_replace", "full_rewrite"):
        return EditResult(
            success=False, mode=mode, file_path=file_path,
            error="INVALID_INPUT",
            message=f"Invalid mode: {mode}. Use 'search_replace' or 'full_rewrite'.",
        ).__dict__

    if not await sandbox.file_exists(file_path):
        return EditResult(
            success=False, mode=mode, file_path=file_path,
            error="FILE_NOT_FOUND", message=f"File not found: {file_path}",
        ).__dict__

    if mode == "search_replace" and (not edits or not isinstance(edits, list)):
        return EditResult(
            success=False, mode=mode, file_path=file_path,
            error="INVALID_INPUT",
            message="search_replace mode requires a non-empty 'edits' list.",
        ).__dict__

    if mode == "full_rewrite" and new_content is None:
        return EditResult(
            success=False, mode=mode, file_path=file_path,
            error="INVALID_INPUT", message="full_rewrite mode requires 'new_content'.",
        ).__dict__

    try:
        original_content = await sandbox.read_file(file_path)
    except Exception as e:
        return EditResult(
            success=False, mode=mode, file_path=file_path,
            error="READ_FAILED", message=f"Failed to read file: {e}",
        ).__dict__

    backup_path = None
    if backup:
        backup_path = file_path + ".bak"
        try:
            await sandbox.write_file(backup_path, original_content)
        except Exception as e:
            return EditResult(
                success=False, mode=mode, file_path=file_path,
                error="BACKUP_FAILED", message=f"Failed to create backup: {e}",
            ).__dict__

    if mode == "full_rewrite":
        diff_text = _compute_diff(original_content, new_content, file_path)
        stats = _compute_stats(original_content, new_content)

        try:
            await sandbox.write_file(file_path, new_content)
        except Exception as e:
            return EditResult(
                success=False, mode=mode, file_path=file_path, backup_path=backup_path,
                error="WRITE_FAILED", message=f"Failed to write file: {e}",
            ).__dict__

        return EditResult(
            success=True, mode=mode, file_path=file_path, backup_path=backup_path,
            stats=stats, diff=diff_text,
        ).__dict__

    # search_replace via shared core logic
    content, block_results, all_success = apply_edits_to_content(
        original_content, edits, match_strategy, fuzzy_threshold,
    )

    diff_text = _compute_diff(original_content, content, file_path)
    stats = _compute_stats(original_content, content)

    if content != original_content:
        try:
            await sandbox.write_file(file_path, content)
        except Exception as e:
            return EditResult(
                success=False, mode=mode, file_path=file_path, backup_path=backup_path,
                edit_results=[r.__dict__ for r in block_results],
                error="WRITE_FAILED", message=f"Failed to write file: {e}",
            ).__dict__

    result = EditResult(
        success=all_success,
        mode=mode,
        file_path=file_path,
        backup_path=backup_path,
        edit_results=[r.__dict__ for r in block_results],
        stats=stats,
        diff=diff_text,
    )

    if not all_success:
        failed = [r for r in block_results if r.status == "failed"]
        result.error = "MATCH_NOT_FOUND"
        result.message = f"{len(failed)} of {len(edits)} edit(s) failed to apply."

    return result.__dict__
