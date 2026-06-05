"""
Tutorial 21: MCP stdio tools via setup_mcp.

Prerequisites:
  - pip install "alphora[mcp]"
  - Node.js + npx (for filesystem MCP server example)
  - LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM (for Section 2)

Run:
  python tutorials/21_mcp_stdio.py
"""

import asyncio
import os
import tempfile
from pathlib import Path


async def list_tools_only() -> None:
    """Connect to MCP and print discovered tools (no LLM)."""
    try:
        from alphora.mcp import setup_mcp
    except ImportError as e:
        print(f"[Skip] {e}")
        return

    workspace = tempfile.mkdtemp(prefix="alphora_mcp_")
    print(f"MCP workspace: {workspace}")

    async with setup_mcp(
        servers=[
            {
                "name": "filesystem",
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    workspace,
                ],
            },
        ],
    ) as tools:
        print(f"Discovered {len(tools)} tool(s):")
        for t in tools:
            print(f"  - {t.name}: {t.description[:80]}...")


async def react_with_mcp() -> None:
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("\n[Skip Section 2] Set LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM.")
        return

    try:
        from alphora.mcp import setup_mcp
    except ImportError as e:
        print(f"\n[Skip Section 2] {e}")
        return

    from alphora.agent import ReActAgent
    from alphora.models import OpenAILike

    workspace = Path(tempfile.mkdtemp(prefix="alphora_mcp_run_"))
    (workspace / "hello.txt").write_text("hello from tutorial 21\n", encoding="utf-8")

    llm = OpenAILike()
    async with setup_mcp(
        servers=[
            {
                "name": "filesystem",
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    str(workspace),
                ],
            },
        ],
    ) as tools:
        agent = ReActAgent(
            llm=llm,
            tools=tools,
            system_prompt=(
                "你是文件助手。使用 filesystem__ 开头的 MCP 工具操作文件。"
                "工作区根目录即 MCP server 挂载路径。"
            ),
            max_iterations=10,
        )
        result = await agent.run(
            f"工作区里有哪些文件？如有 hello.txt 请说明其内容。路径: {workspace}"
        )
        print("\nAgent result:")
        print(result[:800] if result else "(empty)")


async def main() -> None:
    print("=== 1. setup_mcp: discover tools ===")
    await list_tools_only()

    print("\n=== 2. ReActAgent + MCP ===")
    await react_with_mcp()


if __name__ == "__main__":
    asyncio.run(main())
