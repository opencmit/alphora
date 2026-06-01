"""从流式工具调用中增量提取指定参数并以自定义 content_type 输出。

需要配合 ``stream_tool_calls=True`` 使用，否则流中不会出现 ``tool_call`` /
``tool_call_args`` 类型的 chunk。

示例 -- 单工具::

    from alphora.postprocess import ToolCallArgStreamPP

    pp = ToolCallArgStreamPP(
        tool_name="run_bash",
        arg_name="command",
        content_type="terminal",
    )
    result = prompt.call(
        query="执行 ls 命令",
        tools=tools,
        is_stream=True,
        stream_tool_calls=True,
        postprocessor=pp,
    )

示例 -- 多工具::

    pp = ToolCallArgStreamPP(mappings={
        "run_bash":   ("command", "terminal"),
        "run_python": ("code", "python"),
    })

示例 -- 单工具多参数（一个工具同时提取多个参数，各自走不同 content_type）::

    pp = ToolCallArgStreamPP(mappings={
        "run_bash": [("command", "terminal"), ("reason", "think")],
    })

    # mappings 的 value 既可是单个 ``(arg_name, content_type)``，
    # 也可是它们的列表 ``[(arg_name, content_type), ...]``，两种可混用。
"""

from __future__ import annotations

import json
from typing import Dict, Iterator, AsyncIterator, List, Optional, Tuple, Union

from json_repair import repair_json

from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.postprocess.base_pp import BasePostProcessor

# mappings 中单个工具的取值：一个 (arg_name, content_type)，或它们的列表。
ArgSpec = Tuple[str, str]
ToolMapValue = Union[ArgSpec, List[ArgSpec]]


def _normalize_specs(value: ToolMapValue) -> List[ArgSpec]:
    """把工具映射值归一化为 ``[(arg_name, content_type), ...]``。

    兼容两种写法：
    - 单参数元组 ``("command", "terminal")``；
    - 多参数列表 ``[("command", "terminal"), ("reason", "think")]``。
    """
    if isinstance(value, list):
        items = value
    elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        items = [value]
    else:
        items = list(value)
    return [tuple(it) for it in items]


class ToolCallArgStreamPP(BasePostProcessor):
    """流式工具调用参数提取后处理器。

    拦截流中的 ``tool_call`` / ``tool_call_args`` chunk，对匹配的工具调用
    增量提取指定参数值，以自定义 ``content_type`` 重新 yield。非匹配的
    chunk 和普通内容原样透传。
    """

    def __init__(
        self,
        tool_name: Optional[str] = None,
        arg_name: Optional[str] = None,
        content_type: str = "text",
        mappings: Optional[Dict[str, ToolMapValue]] = None,
        pass_through_unmatched: bool = True,
    ):
        """
        Args:
            tool_name: 单工具模式 -- 要拦截的工具名称。
            arg_name: 单工具模式 -- 要提取的参数名。
            content_type: 单工具模式 -- 提取内容的 content_type。
            mappings: 多工具模式 -- ``{tool_name: value}``，其中 ``value`` 既可是单个
                ``(arg_name, content_type)``，也可是它们的列表
                ``[(arg_name, content_type), ...]``（同一工具提取多个参数）。
                与 ``tool_name``/``arg_name``/``content_type`` 二选一。
            pass_through_unmatched: 不匹配的 ``tool_call`` / ``tool_call_args``
                chunk 是否透传。默认 True。
        """
        if tool_name is not None and mappings is not None:
            raise ValueError("tool_name 和 mappings 不能同时指定")
        if tool_name is None and mappings is None:
            raise ValueError("必须指定 tool_name 或 mappings")
        if tool_name is not None and arg_name is None:
            raise ValueError("使用 tool_name 时必须同时指定 arg_name")

        # 内部统一存成 {tool_name: [(arg_name, content_type), ...]}
        if mappings is not None:
            self.mappings: Dict[str, List[ArgSpec]] = {
                name: _normalize_specs(value) for name, value in mappings.items()
            }
        else:
            self.mappings = {tool_name: [(arg_name, content_type)]}

        self.pass_through_unmatched = pass_through_unmatched

    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        pp = self

        class ToolCallArgStreamGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, original_generator):
                super().__init__(original_generator.content_type)
                self.original_generator = original_generator

            def _make_state(self):
                """创建处理状态（每次迭代独立）"""
                return {
                    "active_tools": {},
                    "arg_buffers": {},
                    "last_emitted": {},
                    "current_index": None,
                }

            def _handle_tool_call(self, content: str, state: dict):
                """处理 tool_call chunk，返回要 yield 的 output 列表"""
                tc_info = json.loads(content)
                idx = tc_info.get("index", 0)
                name = tc_info.get("name", "")
                state["current_index"] = idx

                if name in pp.mappings:
                    state["active_tools"][idx] = name
                    state["arg_buffers"][idx] = ""
                    # 按参数名分桶记录各自已发出的内容
                    state["last_emitted"][idx] = {}
                    # 即便命中映射，也把 tool_call（工具名）透传给下游，
                    # 否则客户端会完全看不到被拦截工具的名字。
                    return [GeneratorOutput(content=content, content_type="tool_call")]

                if pp.pass_through_unmatched:
                    return [GeneratorOutput(content=content, content_type="tool_call")]
                return []

            def _handle_tool_call_args(self, content: str, state: dict):
                """处理 tool_call_args chunk，返回要 yield 的 output 列表

                命中映射的工具可能配置了多个参数，逐个提取各自的增量，
                各带自己的 content_type 产出。
                """
                idx = state["current_index"]

                if idx is not None and idx in state["active_tools"]:
                    tool_name = state["active_tools"][idx]
                    state["arg_buffers"][idx] += content

                    outputs = []
                    for arg_name, out_content_type in pp.mappings[tool_name]:
                        incremental = self._extract_incremental(idx, arg_name, state)
                        if incremental:
                            outputs.append(GeneratorOutput(
                                content=incremental,
                                content_type=out_content_type,
                            ))
                    return outputs

                if pp.pass_through_unmatched:
                    return [GeneratorOutput(content=content, content_type="tool_call_args")]
                return []

            def _extract_incremental(self, index: int, arg_name: str, state: dict) -> Optional[str]:
                buffer = state["arg_buffers"][index]

                value = self._extract_arg_value(buffer, arg_name)
                if value is None:
                    return None

                emitted = state["last_emitted"][index]
                last = emitted.get(arg_name, "")
                if value.startswith(last):
                    incremental = value[len(last):]
                    if incremental:
                        emitted[arg_name] = value
                        return incremental
                elif not last:
                    emitted[arg_name] = value
                    return value
                return None

            def _extract_arg_value(self, buffer: str, arg_name: str) -> Optional[str]:
                """从（可能不完整的）JSON buffer 中提取指定 key 的值。

                通过直接解析 JSON 字符串结构定位目标 key，
                避免 repair_json 在值含冒号时将其误判为键值分隔符。
                """
                val_pos = self._find_value_start(buffer, arg_name)
                if val_pos < 0 or val_pos >= len(buffer):
                    return None

                if buffer[val_pos] == '"':
                    return self._decode_json_string(buffer, val_pos)

                try:
                    repaired = repair_json(buffer)
                    parsed = json.loads(repaired)
                    v = parsed.get(arg_name)
                    return str(v) if v is not None else None
                except Exception:
                    return None

            @staticmethod
            def _find_value_start(buffer: str, key: str) -> int:
                """在 JSON buffer 中定位 *key* 对应 value 的起始偏移。

                正确跳过字符串内部出现的同名文本，仅匹配顶层 key。
                只有当 ``"key"`` 后面紧跟 ``:`` 时才视为匹配。
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

            @staticmethod
            def _decode_json_string(buffer: str, quote_pos: int) -> Optional[str]:
                """从 *quote_pos* 处的 ``"`` 开始解码 JSON 字符串。

                若 buffer 不完整（未遇到闭合引号），返回已解码部分。
                """
                _ESC = {'"': '"', '\\': '\\', '/': '/', 'n': '\n',
                        'r': '\r', 't': '\t', 'b': '\b', 'f': '\f'}
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

            def generate(self) -> Iterator[GeneratorOutput]:
                state = self._make_state()
                for output in self.original_generator:
                    ctype = output.content_type

                    if ctype == "tool_call":
                        for result in self._handle_tool_call(output.content, state):
                            yield result
                        continue

                    if ctype == "tool_call_args":
                        for result in self._handle_tool_call_args(output.content, state):
                            yield result
                        continue

                    yield output

            async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
                state = self._make_state()
                async for output in self.original_generator:
                    ctype = output.content_type

                    if ctype == "tool_call":
                        for result in self._handle_tool_call(output.content, state):
                            yield result
                        continue

                    if ctype == "tool_call_args":
                        for result in self._handle_tool_call_args(output.content, state):
                            yield result
                        continue

                    yield output

        return ToolCallArgStreamGenerator(generator)
