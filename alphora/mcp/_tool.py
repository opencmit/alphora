# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""MCP tool bridge: wraps MCP server tools as Alphora Tool instances."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Union

from pydantic import BaseModel, create_model

from alphora.tools.core import Tool
from alphora.tools.exceptions import ToolValidationError

if TYPE_CHECKING:
    from mcp import ClientSession

_INVALID_NAME_CHARS = re.compile(r"[^a-zA-Z0-9_-]")


def mcp_tool_name(server_name: str, tool_name: str) -> str:
    """Alphora-visible name: ``{server}__{tool}`` (sanitized for OpenAI)."""
    raw = f"{server_name}__{tool_name}"
    return _INVALID_NAME_CHARS.sub("_", raw)


def normalize_input_schema(input_schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensure OpenAI-compatible parameters object from MCP inputSchema."""
    if not input_schema:
        return {"type": "object", "properties": {}}
    if input_schema.get("type") == "object":
        return {
            "type": "object",
            "properties": input_schema.get("properties") or {},
            "required": input_schema.get("required") or [],
        }
    return {
        "type": "object",
        "properties": {"value": input_schema},
    }


def _serialize_block(block: Any) -> str:
    """Serialize a single MCP content block to text."""
    text = getattr(block, "text", None)
    if text is not None:
        return text
    if isinstance(block, dict):
        if block.get("type") == "text" and "text" in block:
            return block["text"]
        return json.dumps(block, ensure_ascii=False)
    if hasattr(block, "model_dump_json"):
        try:
            return block.model_dump_json()
        except Exception:
            pass
    return str(block)


def format_call_tool_result(result: Any) -> str:
    """Serialize MCP CallToolResult to a string for the LLM."""
    prefix = "Error: " if getattr(result, "isError", False) else ""

    parts: List[str] = [_serialize_block(b) for b in (getattr(result, "content", None) or [])]

    if parts:
        return prefix + "\n".join(parts)
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return prefix + json.dumps(structured, ensure_ascii=False)
    return prefix + "MCP tool returned no content."


def _passthrough_schema(tool_name: str) -> type[BaseModel]:
    """Minimal schema so ToolExecutor can pass kwargs through validate_args."""
    model_name = f"Mcp{tool_name.replace('__', '_').title().replace('_', '')}Args"
    return create_model(model_name)


class MCPTool(Tool):
    """
    Alphora Tool backed by an MCP ``tools/call`` on a connected ClientSession.
    """

    mcp_tool_name: str
    input_schema: Dict[str, Any]

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_mcp_tool(
        cls,
        *,
        server_name: str,
        mcp_tool: Any,
        session: "ClientSession",
        lock: Optional[asyncio.Lock] = None,
        tool_timeout: Optional[float] = None,
    ) -> "MCPTool":
        if isinstance(mcp_tool, dict):
            raw_name = mcp_tool.get("name")
            description = mcp_tool.get("description") or "MCP tool"
            input_schema = mcp_tool.get("inputSchema")
        else:
            raw_name = getattr(mcp_tool, "name", None)
            description = getattr(mcp_tool, "description", None) or "MCP tool"
            input_schema = getattr(mcp_tool, "inputSchema", None)
        if hasattr(input_schema, "model_dump"):
            input_schema = input_schema.model_dump()
        elif input_schema is not None and not isinstance(input_schema, dict):
            input_schema = dict(input_schema)

        alphora_name = mcp_tool_name(server_name, raw_name)
        schema_model = _passthrough_schema(alphora_name)
        call_lock = lock or asyncio.Lock()

        async def _invoke(**kwargs: Any) -> str:
            # Serialize concurrent calls on the same MCP session (single transport).
            async with call_lock:
                call_kwargs: Dict[str, Any] = {}
                if tool_timeout is not None:
                    call_kwargs["read_timeout_seconds"] = tool_timeout
                result = await session.call_tool(raw_name, kwargs or None, **call_kwargs)
            # MCP tool-level errors are returned to the LLM as normal content,
            # not raised, so the model can read and react to them.
            return format_call_tool_result(result)

        return cls(
            name=alphora_name,
            description=description.strip(),
            func=_invoke,
            args_schema=schema_model,
            is_async=True,
            mcp_tool_name=raw_name,
            input_schema=normalize_input_schema(input_schema),
        )

    @property
    def openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def validate_args(self, tool_input: Union[str, Dict]) -> Dict[str, Any]:
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except json.JSONDecodeError as e:
                raise ToolValidationError(
                    f"Arguments validation failed for tool '{self.name}': invalid JSON"
                ) from e
        if not isinstance(tool_input, dict):
            raise ToolValidationError(
                f"Arguments validation failed for tool '{self.name}': expected object"
            )
        return tool_input
