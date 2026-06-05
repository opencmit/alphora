# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
MCP setup — connect MCP servers and yield Alphora Tool list.

Supports three transports: ``stdio`` (local subprocess), ``sse`` and
``streamable_http`` (remote URL).

Usage::

    # local stdio
    async with setup_mcp(servers=[{"name": "fs", "command": "npx", "args": [...]}]) as tools:
        agent = ReActAgent(llm=llm, tools=tools)
        await agent.run("...")

    # remote URL
    async with setup_mcp(servers=[{
        "name": "wiki", "transport": "sse", "url": "https://mcp.example.com/sse",
    }]) as tools:
        ...
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Union

from alphora.tools.core import Tool

from ._tool import MCPTool

logger = logging.getLogger(__name__)

_MCP_INSTALL_HINT = 'Install MCP support with: pip install "alphora[mcp]"'

_REMOTE_TRANSPORTS = ("sse", "streamable_http")
_VALID_TRANSPORTS = ("stdio",) + _REMOTE_TRANSPORTS

DEFAULT_TOOL_TIMEOUT = 30.0


def _require_mcp() -> None:
    try:
        import mcp  # noqa: F401
    except ImportError as e:
        raise ImportError(_MCP_INSTALL_HINT) from e


def _infer_transport(cfg: Dict[str, Any]) -> str:
    explicit = cfg.get("transport")
    if explicit:
        if explicit not in _VALID_TRANSPORTS:
            raise ValueError(
                f"Invalid transport '{explicit}'. Must be one of {_VALID_TRANSPORTS}"
            )
        return explicit
    if cfg.get("command"):
        return "stdio"
    if cfg.get("url"):
        return "streamable_http"
    raise ValueError(
        "MCP server config requires either 'command' (stdio) or 'url' (remote)"
    )


def _normalize_server(server: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    if isinstance(server, dict):
        cfg = dict(server)
    elif hasattr(server, "model_dump"):
        cfg = server.model_dump()
    else:
        raise TypeError(
            "Each server entry must be a dict (name + command/args for stdio, "
            "or name + url for remote)"
        )

    name = cfg.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("MCP server config requires non-empty string 'name'")

    transport = _infer_transport(cfg)
    out: Dict[str, Any] = {"name": name, "transport": transport}

    if transport == "stdio":
        command = cfg.get("command")
        args = cfg.get("args")
        if not command or not isinstance(command, str):
            raise ValueError(f"MCP server '{name}' requires string 'command'")
        if args is None:
            args = []
        if not isinstance(args, list):
            raise ValueError(f"MCP server '{name}' requires list 'args'")
        out.update(
            command=command,
            args=[str(a) for a in args],
            env=cfg.get("env"),
            cwd=cfg.get("cwd"),
        )
    else:
        url = cfg.get("url")
        if not url or not isinstance(url, str):
            raise ValueError(f"MCP server '{name}' ({transport}) requires string 'url'")
        out.update(
            url=url,
            headers=cfg.get("headers"),
            timeout=cfg.get("timeout"),
            sse_read_timeout=cfg.get("sse_read_timeout"),
        )

    return out


async def _open_session(stack: AsyncExitStack, server: Dict[str, Any]) -> Any:
    from mcp import ClientSession

    transport = server["transport"]

    if transport == "stdio":
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        params_kwargs: Dict[str, Any] = {
            "command": server["command"],
            "args": server["args"],
        }
        if server.get("env") is not None:
            params_kwargs["env"] = server["env"]
        if server.get("cwd") is not None:
            params_kwargs["cwd"] = str(server["cwd"])
        server_params = StdioServerParameters(**params_kwargs)
        read, write = await stack.enter_async_context(stdio_client(server_params))

    elif transport == "sse":
        from mcp.client.sse import sse_client

        kwargs: Dict[str, Any] = {"url": server["url"]}
        if server.get("headers") is not None:
            kwargs["headers"] = server["headers"]
        if server.get("timeout") is not None:
            kwargs["timeout"] = server["timeout"]
        if server.get("sse_read_timeout") is not None:
            kwargs["sse_read_timeout"] = server["sse_read_timeout"]
        read, write = await stack.enter_async_context(sse_client(**kwargs))

    elif transport == "streamable_http":
        from mcp.client.streamable_http import streamablehttp_client

        kwargs = {"url": server["url"]}
        if server.get("headers") is not None:
            kwargs["headers"] = server["headers"]
        if server.get("timeout") is not None:
            kwargs["timeout"] = server["timeout"]
        if server.get("sse_read_timeout") is not None:
            kwargs["sse_read_timeout"] = server["sse_read_timeout"]
        # streamable_http returns a third element (session id getter); ignore it.
        read, write, _ = await stack.enter_async_context(streamablehttp_client(**kwargs))

    else:  # pragma: no cover - guarded by _infer_transport
        raise ValueError(f"Unsupported transport: {transport}")

    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    logger.info("MCP server connected: %s (%s)", server["name"], transport)
    return session


async def _discover_tools(
    servers: List[Dict[str, Any]],
    stack: AsyncExitStack,
    tool_timeout: float,
    fail_fast: bool,
) -> List[Tool]:
    tools: List[Tool] = []

    for server in servers:
        name = server["name"]
        try:
            session = await _open_session(stack, server)
            list_result = await session.list_tools()
        except Exception as e:
            msg = f"MCP server '{name}' ({server['transport']}) 连接失败: {e}"
            if fail_fast:
                raise RuntimeError(msg) from e
            logger.warning(msg)
            continue

        lock = asyncio.Lock()
        for mcp_tool in list_result.tools:
            tools.append(
                MCPTool.from_mcp_tool(
                    server_name=name,
                    mcp_tool=mcp_tool,
                    session=session,
                    lock=lock,
                    tool_timeout=tool_timeout,
                )
            )

        logger.info("MCP server %s: discovered %d tool(s)", name, len(list_result.tools))

    return tools


@asynccontextmanager
async def setup_mcp(
    servers: List[Union[Dict[str, Any], Any]],
    tool_timeout: float = DEFAULT_TOOL_TIMEOUT,
    fail_fast: bool = False,
) -> AsyncIterator[List[Tool]]:
    """
    Connect to one or more MCP servers and yield Alphora ``Tool`` instances.

    Args:
        servers: List of dicts. Each dict has a ``name`` plus either:
            - stdio: ``command`` (str), ``args`` (list[str]), optional ``env``, ``cwd``
            - remote: ``url`` (str), optional ``headers``, ``timeout``, ``sse_read_timeout``,
              and ``transport`` ("sse" | "streamable_http"; inferred as
              "streamable_http" when only ``url`` is given).
        tool_timeout: Per-call read timeout (seconds) for ``tools/call``.
        fail_fast: If True, a server connection failure raises; otherwise the
            failed server is skipped (default) so other servers still work.

    Yields:
        List of :class:`~alphora.tools.core.Tool` ready for ``ReActAgent(tools=...)``.

    Example::

        async with setup_mcp(servers=[{
            "name": "wiki", "transport": "sse",
            "url": "https://mcp.deepwiki.com/sse",
        }]) as tools:
            agent = ReActAgent(llm=llm, tools=tools)
            await agent.run("...")
    """
    _require_mcp()

    if not servers:
        raise ValueError("setup_mcp requires at least one server in 'servers'")

    normalized = [_normalize_server(s) for s in servers]
    names = [s["name"] for s in normalized]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate MCP server 'name' values are not allowed")

    async with AsyncExitStack() as stack:
        tools = await _discover_tools(normalized, stack, tool_timeout, fail_fast)
        try:
            yield tools
        finally:
            logger.debug("MCP connections closed")
