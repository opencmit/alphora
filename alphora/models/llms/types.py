# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

"""
工具调用类型定义

ToolCall 是 LLM 返回工具调用时的响应对象。
"""

import json
from typing import List, Dict, Any, Optional


class ToolCall(list):
    """
    工具调用响应对象

    本质上是一个列表，包含所有工具调用，同时携带额外元数据。

    Attributes:
        content: LLM 返回的文本内容 (工具调用时通常为 None)

    Properties:
        tool_calls: 工具调用列表 (返回自身的副本)
        has_tool_calls: 是否有工具调用

    Example:
        # 从 LLM 响应获取
        response = await prompt.acall(query="查天气", tools=tools)

        # 检查是否有工具调用
        if response.has_tool_calls:
            for tc in response.tool_calls:
                print(tc["function"]["name"])
        else:
            print(response.content)
    """

    def __init__(self, tool_calls: List[Dict[str, Any]], content: Optional[str] = None):
        """
        Args:
            tool_calls: 工具调用列表
            content: 文本内容 (可选)
        """
        super().__init__(tool_calls or [])
        self.content = content

    @property
    def tool_calls(self) -> List[Dict[str, Any]]:
        """
        返回工具调用列表

        这是为了 API 一致性，让 response.tool_calls 这种写法能用。
        """
        return list(self) if self else []

    @property
    def has_tool_calls(self) -> bool:
        """是否有工具调用"""
        return len(self) > 0

    def get_tool_names(self) -> List[str]:
        """获取所有调用的工具名称"""
        return [tc.get("function", {}).get("name", "") for tc in self]

    def get_tool_call_ids(self) -> List[str]:
        """获取所有工具调用 ID"""
        return [tc.get("id", "") for tc in self]

    def format_details(self, indent: int = 2) -> str:
        """
        格式化展示工具调用详情 (面向人类)

        Args:
            indent: 缩进空格数

        Returns:
            格式化的字符串

        Example:
            print(response.format_details())
            工具调用详情 (共 2 个)
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            [1] get_weather
                ID: call_abc123
                参数:
                  • city: "北京"
                  • unit: "celsius"

            [2] get_time
                ID: call_def456
                参数:
                  • timezone: "Asia/Shanghai"
        """
        if not self:
            return "无工具调用"

        lines = [
            f"工具调用详情 (共 {len(self)} 个)",
            "━" * 30
        ]

        for i, tc in enumerate(self, 1):
            func = tc.get("function", {})
            name = func.get("name", "unknown")
            call_id = tc.get("id", "unknown")
            args_str = func.get("arguments", "{}")

            # 解析参数
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except:
                args = {"_raw": args_str}

            lines.append(f"\n[{i}] {name}")
            lines.append(f"{' ' * indent}ID: {call_id}")

            if args:
                lines.append(f"{' ' * indent}参数:")
                for key, value in args.items():
                    # 格式化值的显示
                    if isinstance(value, str):
                        display_value = f'"{value}"'
                    elif isinstance(value, (dict, list)):
                        display_value = json.dumps(value, ensure_ascii=False)
                    else:
                        display_value = str(value)

                    # 截断过长的值
                    if len(display_value) > 50:
                        display_value = display_value[:47] + "..."

                    lines.append(f"{' ' * indent}  • {key}: {display_value}")
            else:
                lines.append(f"{' ' * indent}参数: (无)")

        lines.append("━" * 30)

        return "\n".join(lines)

    def pretty_print(self, indent: int = 2) -> None:
        """
        打印工具调用详情 (面向人类)

        Args:
            indent: 缩进空格数

        Example:
            >>> response.pretty_print()
            工具调用详情 (共 1 个)
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            [1] get_weather
                ID: call_abc123
                参数:
                  • city: "北京"
        """
        print(self.format_details(indent))

    def to_summary(self) -> str:
        """
        生成简短的单行摘要

        Returns:
            单行摘要字符串

        Example:
            >>> response.to_summary()
            '调用 2 个工具: get_weather(city="北京"), get_time(timezone="Asia/Shanghai")'
        """
        if not self:
            return "无工具调用"

        summaries = []

        for tc in self:
            func = tc.get("function", {})
            name = func.get("name", "unknown")
            args_str = func.get("arguments", "{}")

            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except:
                args = {}

            # 生成简短参数摘要
            if args:
                params = []
                for k, v in list(args.items())[:2]:  # 最多显示 2 个参数
                    if isinstance(v, str):
                        v_str = f'"{v[:10]}{"..." if len(v) > 10 else ""}"'
                    else:
                        v_str = str(v)[:15]
                    params.append(f'{k}={v_str}')

                if len(args) > 2:
                    params.append("...")

                summaries.append(f"{name}({', '.join(params)})")
            else:
                summaries.append(f"{name}()")

        return f"调用 {len(self)} 个工具: {', '.join(summaries)}"

    def __repr__(self):
        if self.content:
            return f"{self.content}"
        elif self:
            return f"ToolCall({super().__repr__()})"
        else:
            return "ToolCall([])"

    def __str__(self):
        if self.content:
            return self.content
        elif self:
            names = self.get_tool_names()
            return f"[调用工具: {', '.join(names)}]"
        else:
            return ""

    def __bool__(self):
        """
        布尔判断：有工具调用或有内容时为 True
        """
        return len(self) > 0 or bool(self.content)