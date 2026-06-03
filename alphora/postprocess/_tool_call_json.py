"""流式工具调用参数的增量 JSON 解析工具。

这些函数从一段 **可能不完整** 的 JSON buffer（工具调用 arguments 的累积片段）中
定位并提取指定 key 的值，供流式后处理器增量取参使用。

被 :mod:`tool_call_arg_stream` 与 :mod:`tool_call_render` 共享，避免重复实现。
"""

from __future__ import annotations

from typing import Optional

from json_repair import repair_json
import json

# JSON 字符串转义表
_ESC = {'"': '"', '\\': '\\', '/': '/', 'n': '\n',
        'r': '\r', 't': '\t', 'b': '\b', 'f': '\f'}


def find_value_start(buffer: str, key: str) -> int:
    """在 JSON buffer 中定位 *key* 对应 value 的起始偏移。

    正确跳过字符串内部出现的同名文本，仅匹配顶层 key。
    只有当 ``"key"`` 后面紧跟 ``:`` 时才视为匹配。

    Returns:
        value 第一个非空白字符的偏移；找不到返回 -1。
    """
    target = f'"{key}"'
    tlen = len(target)
    i, n = 0, len(buffer)
    while i < n:
        ch = buffer[i]
        if ch == '"':
            if buffer[i:i + tlen] == target:
                j = i + tlen
                while j < n and buffer[j] in ' \t\n\r':
                    j += 1
                if j < n and buffer[j] == ':':
                    j += 1
                    while j < n and buffer[j] in ' \t\n\r':
                        j += 1
                    return j
            # 跳过这一整个字符串（含转义），避免把字符串内容误当 key
            i += 1
            while i < n:
                if buffer[i] == '\\':
                    i += 2
                    continue
                if buffer[i] == '"':
                    i += 1
                    break
                i += 1
        else:
            i += 1
    return -1


def decode_json_string(buffer: str, quote_pos: int) -> Optional[str]:
    """从 *quote_pos* 处的 ``"`` 开始解码一个 JSON 字符串。

    若 buffer 不完整（未遇到闭合引号），返回已解码的部分。
    """
    if quote_pos < 0 or quote_pos >= len(buffer) or buffer[quote_pos] != '"':
        return None
    i = quote_pos + 1
    n = len(buffer)
    parts = []
    while i < n:
        ch = buffer[i]
        if ch == '\\':
            if i + 1 >= n:
                break
            nc = buffer[i + 1]
            if nc in _ESC:
                parts.append(_ESC[nc])
                i += 2
            elif nc == 'u':
                if i + 5 < n:
                    try:
                        parts.append(chr(int(buffer[i + 2:i + 6], 16)))
                    except ValueError:
                        parts.append(nc)
                    i += 6
                else:
                    break
            else:
                parts.append(nc)
                i += 2
        elif ch == '"':
            return ''.join(parts)
        else:
            parts.append(ch)
            i += 1
    return ''.join(parts) if parts else None


def _extract_scalar(buffer: str, val_pos: int) -> Optional[str]:
    """提取非字符串值（数字 / 布尔 / null / 对象 / 数组）。

    为避免流式中途把不完整 token 误解析成垃圾（如 ``true`` 解析成 ``"tr"``），
    只有当该值在 buffer 中 **已经结束**（遇到顶层 ``,`` 或闭合的 ``}`` / ``]``）
    时才解析并返回；否则视为尚未完整，返回 ``None`` 等待更多片段。
    """
    n = len(buffer)
    j = val_pos
    depth = 0
    in_str = False
    while j < n:
        ch = buffer[j]
        if in_str:
            if ch == '\\':
                j += 2
                continue
            if ch == '"':
                in_str = False
            j += 1
            continue
        if ch == '"':
            in_str = True
            j += 1
            continue
        if ch in '[{':
            depth += 1
            j += 1
            continue
        if ch in ']}':
            if depth == 0:
                break          # 闭合的是外层对象/数组 -> value 已结束
            depth -= 1
            j += 1
            continue
        if ch == ',' and depth == 0:
            break              # 顶层逗号 -> value 已结束
        j += 1

    if j >= n:
        return None            # 没遇到终止符，value 还不完整

    token = buffer[val_pos:j].strip()
    if not token:
        return None
    try:
        parsed = json.loads(token)
    except Exception:
        try:
            parsed = json.loads(repair_json(token))
        except Exception:
            return None
    return str(parsed) if parsed is not None else None


def extract_arg_value(buffer: str, arg_name: str) -> Optional[str]:
    """从（可能不完整的）JSON buffer 中提取指定 key 的值（始终转成 str）。

    字符串值边解码边返回（增量友好）；非字符串值（数字/布尔/对象等）
    在值结束后一次性返回。提取不到或值为 ``null`` 返回 ``None``。
    """
    val_pos = find_value_start(buffer, arg_name)
    if val_pos < 0 or val_pos >= len(buffer):
        return None

    if buffer[val_pos] == '"':
        return decode_json_string(buffer, val_pos)

    return _extract_scalar(buffer, val_pos)
