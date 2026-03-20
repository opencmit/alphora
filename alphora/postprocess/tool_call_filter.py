"""按工具名称过滤 ToolCall 中的调用项。

示例::

    from alphora.postprocess import ToolCallFilterPP

    # 只保留 get_weather
    pp = ToolCallFilterPP(include_tools=["get_weather"])
    result = prompt.call(query="查天气", tools=tools, postprocessor=pp)

    # 排除 debug_tool
    pp = ToolCallFilterPP(exclude_tools=["debug_tool"])

    # 同时使用（先 include 白名单，再 exclude 黑名单）
    pp = ToolCallFilterPP(include_tools=["a", "b", "c"], exclude_tools=["c"])
"""

from __future__ import annotations

import json
from typing import List, Optional, TYPE_CHECKING

from alphora.postprocess.base_pp import BasePostProcessor

if TYPE_CHECKING:
    from alphora.models.llms.types import ToolCall


class ToolCallFilterPP(BasePostProcessor):
    """按工具名称对 ToolCall 列表做白名单 / 黑名单过滤。"""

    def __init__(
        self,
        include_tools: Optional[List[str]] = None,
        exclude_tools: Optional[List[str]] = None,
    ):
        """
        Args:
            include_tools: 白名单，只保留这些名称的工具调用。为 None 表示不做白名单限制。
            exclude_tools: 黑名单，排除这些名称的工具调用。为 None 表示不做黑名单限制。
        """
        self.include_tools = set(include_tools) if include_tools else None
        self.exclude_tools = set(exclude_tools) if exclude_tools else None

    def _get_tool_name(self, tc: dict) -> str:
        return tc.get("function", {}).get("name", "")

    def _should_keep(self, tc: dict) -> bool:
        name = self._get_tool_name(tc)
        if self.include_tools is not None and name not in self.include_tools:
            return False
        if self.exclude_tools is not None and name in self.exclude_tools:
            return False
        return True

    def process_tool_call(self, tool_call: "ToolCall") -> "ToolCall":
        from alphora.models.llms.types import ToolCall as TC
        filtered = [tc for tc in tool_call if self._should_keep(tc)]
        return TC(tool_calls=filtered, content=tool_call.content)
