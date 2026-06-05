# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""MCP (Model Context Protocol) client integration for Alphora tools."""

from .setup import setup_mcp
from ._tool import MCPTool, format_call_tool_result, mcp_tool_name

__all__ = [
    "setup_mcp",
    "MCPTool",
    "format_call_tool_result",
    "mcp_tool_name",
]
