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
"""

from __future__ import annotations

import json
from typing import Dict, Iterator, AsyncIterator, Optional, Tuple

from json_repair import repair_json

from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.postprocess.base_pp import BasePostProcessor


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
        mappings: Optional[Dict[str, Tuple[str, str]]] = None,
        pass_through_unmatched: bool = True,
    ):
        """
        Args:
            tool_name: 单工具模式 -- 要拦截的工具名称。
            arg_name: 单工具模式 -- 要提取的参数名。
            content_type: 单工具模式 -- 提取内容的 content_type。
            mappings: 多工具模式 -- ``{tool_name: (arg_name, content_type)}``。
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

        if mappings is not None:
            self.mappings = dict(mappings)
        else:
            self.mappings = {tool_name: (arg_name, content_type)}

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
                """处理 tool_call chunk，返回要 yield 的 output 或 None"""
                tc_info = json.loads(content)
                idx = tc_info.get("index", 0)
                name = tc_info.get("name", "")
                state["current_index"] = idx

                if name in pp.mappings:
                    state["active_tools"][idx] = name
                    state["arg_buffers"][idx] = ""
                    state["last_emitted"][idx] = ""
                    return None

                if pp.pass_through_unmatched:
                    return GeneratorOutput(content=content, content_type="tool_call")
                return None

            def _handle_tool_call_args(self, content: str, state: dict):
                """处理 tool_call_args chunk，返回要 yield 的 output 或 None"""
                idx = state["current_index"]

                if idx is not None and idx in state["active_tools"]:
                    tool_name = state["active_tools"][idx]
                    state["arg_buffers"][idx] += content

                    incremental = self._extract_incremental(idx, tool_name, state)
                    if incremental is not None:
                        _, out_content_type = pp.mappings[tool_name]
                        return GeneratorOutput(
                            content=incremental,
                            content_type=out_content_type,
                        )
                    return None

                if pp.pass_through_unmatched:
                    return GeneratorOutput(content=content, content_type="tool_call_args")
                return None

            def _extract_incremental(self, index: int, tool_name: str, state: dict) -> Optional[str]:
                buffer = state["arg_buffers"][index]
                arg_name, _ = pp.mappings[tool_name]
                try:
                    repaired = repair_json(buffer)
                    parsed = json.loads(repaired)
                    value = parsed.get(arg_name)
                    if value is None:
                        return None
                    value = str(value)
                except Exception:
                    return None

                last = state["last_emitted"].get(index, "")
                if value.startswith(last):
                    incremental = value[len(last):]
                    if incremental:
                        state["last_emitted"][index] = value
                        return incremental
                elif not last:
                    state["last_emitted"][index] = value
                    return value
                return None

            def generate(self) -> Iterator[GeneratorOutput]:
                state = self._make_state()
                for output in self.original_generator:
                    ctype = output.content_type

                    if ctype == "tool_call":
                        result = self._handle_tool_call(output.content, state)
                        if result is not None:
                            yield result
                        continue

                    if ctype == "tool_call_args":
                        result = self._handle_tool_call_args(output.content, state)
                        if result is not None:
                            yield result
                        continue

                    yield output

            async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
                state = self._make_state()
                async for output in self.original_generator:
                    ctype = output.content_type

                    if ctype == "tool_call":
                        result = self._handle_tool_call(output.content, state)
                        if result is not None:
                            yield result
                        continue

                    if ctype == "tool_call_args":
                        result = self._handle_tool_call_args(output.content, state)
                        if result is not None:
                            yield result
                        continue

                    yield output

        return ToolCallArgStreamGenerator(generator)
