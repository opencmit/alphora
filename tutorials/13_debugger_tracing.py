"""
Tutorial 13: Debugger / tracer (experimental).

Run:
  python tutorials/13_debugger_tracing.py
"""

import asyncio
import os

from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.tools import tool
from alphora.debugger import tracer


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


async def main() -> None:
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("Missing env vars. Please set LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM.")
        return

    agent = ReActAgent(
        llm=OpenAILike(),
        tools=[add],
        system_prompt="Use tools when needed.",
        max_iterations=3,
        debugger=True,  # Starts debugger server on port 9527
    )

    result = await agent.run("Compute 2 + 5 using the add tool.")
    print("Result:", result)
    print("Debugger UI (experimental): http://localhost:9527/")

    # Read some in-memory stats
    stats = tracer.get_stats()
    print("Tracer stats keys:", list(stats.keys()))


if __name__ == "__main__":
    asyncio.run(main())
