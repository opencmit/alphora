"""
Tutorial 01: Build a ReAct agent with one tool + run_steps.

Prerequisites (set these env vars before running):
  - LLM_API_KEY
  - LLM_BASE_URL
  - DEFAULT_LLM

Run:
  python tutorials/01_basic_react_agent.py
"""

import asyncio
import os

from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.tools import tool
from alphora.sandbox import Sandbox


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


async def main() -> None:
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("Missing env vars. Please set LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM.")
        return

    llm = OpenAILike()
    agent = ReActAgent(
        llm=llm,
        tools=[add],
        system_prompt="You are a helpful assistant. Use tools when needed.",
        max_iterations=5,
    )

    question = "Calculate 37 + 58. Use the add tool."
    result = await agent.run(question)

    print("\nUser:", question)
    print("\nAssistant:", result)

    print("\n=== run_steps (step-by-step) ===")
    async for step in agent.run_steps("Calculate 5 + 7 with the add tool."):
        print(
            f"iter={step.iteration}, action={step.action}, "
            f"final={step.is_final}, content={step.content}"
        )

    print("\n=== ReAct + Sandbox (auto tool registration) ===")
    async with Sandbox.create_local() as sandbox:
        sandbox_agent = ReActAgent(
            llm=llm,
            tools=[add],
            sandbox=sandbox,  # auto registers sandbox tools
            system_prompt="You can use tools and python code when needed.",
            max_iterations=5,
        )
        result = await sandbox_agent.run("Compute 3+4. If needed, use python.")
        print("Sandbox result:", result)


if __name__ == "__main__":
    asyncio.run(main())
