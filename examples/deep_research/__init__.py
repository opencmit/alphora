"""
Deep Research - Alphora Skills 综合示例

展示 Skills + Sandbox + Tools + Agent + Hooks 的完整协作方式。

Quick Start:
    from examples.deep_research.agent import create_deep_research_agent
    from alphora.sandbox import Sandbox

    async with Sandbox(runtime="local") as sandbox:
        agent = await create_deep_research_agent(sandbox=sandbox)
        result = await agent.run("研究 AI Agent 技术趋势")
"""

from .agent import create_deep_research_agent

__all__ = ["create_deep_research_agent"]
