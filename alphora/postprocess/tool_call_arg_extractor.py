"""提取 ToolCall 中特定工具的特定参数。

示例::

    from alphora.postprocess import ToolCallArgExtractorPP

    # 只保留 get_weather 的 city 参数
    pp = ToolCallArgExtractorPP(
        extraction_map={"get_weather": ["city"]},
        keep_unmatched=False,
    )
    result = prompt.call(query="查天气", tools=tools, postprocessor=pp)

    # 链式使用
    pp = ToolCallFilterPP(include_tools=["get_weather"]) >> ToolCallArgExtractorPP(
        extraction_map={"get_weather": ["city"]},
    )
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Union, TYPE_CHECKING

from alphora.postprocess.base_pp import BasePostProcessor

if TYPE_CHECKING:
    from alphora.models.llms.types import ToolCall


class ToolCallArgExtractorPP(BasePostProcessor):
    """从 ToolCall 的工具调用中提取指定参数，丢弃其余参数。

    对于 ``extraction_map`` 中列出的工具，只保留指定的参数 key；
    对于未列出的工具，由 ``keep_unmatched`` 决定是保留还是丢弃整个调用。
    """

    def __init__(
        self,
        extraction_map: Dict[str, Union[List[str], str]],
        keep_unmatched: bool = True,
    ):
        """
        Args:
            extraction_map: 工具名 -> 需要保留的参数名列表（或单个参数名字符串）。
                例如 ``{"get_weather": ["city", "unit"], "search": "query"}``
            keep_unmatched: 不在 extraction_map 中的工具调用是否保留（原样透传）。
                默认 True。
        """
        self.extraction_map: Dict[str, List[str]] = {}
        for name, keys in extraction_map.items():
            if isinstance(keys, str):
                self.extraction_map[name] = [keys]
            else:
                self.extraction_map[name] = list(keys)
        self.keep_unmatched = keep_unmatched

    def _process_single(self, tc: dict) -> Optional[dict]:
        func = tc.get("function", {})
        name = func.get("name", "")

        if name not in self.extraction_map:
            return tc if self.keep_unmatched else None

        desired_keys = self.extraction_map[name]
        args_str = func.get("arguments", "{}")
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except (json.JSONDecodeError, TypeError):
            return tc

        filtered_args = {k: v for k, v in args.items() if k in desired_keys}
        new_func = {**func, "arguments": json.dumps(filtered_args, ensure_ascii=False)}
        return {**tc, "function": new_func}

    def process_tool_call(self, tool_call: "ToolCall") -> "ToolCall":
        from alphora.models.llms.types import ToolCall as TC
        result = []
        for tc in tool_call:
            processed = self._process_single(tc)
            if processed is not None:
                result.append(processed)
        return TC(tool_calls=result, content=tool_call.content)
