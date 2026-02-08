"""
Tutorial 07: ParallelPrompt and the `|` operator.

Run:
  python tutorials/07_prompter_parallel.py
"""

import asyncio
import os

from alphora.prompter import BasePrompt
from alphora.prompter.parallel import ParallelPrompt
from alphora.models import OpenAILike


async def main() -> None:
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("Missing env vars. Please set LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM.")
        return

    llm = OpenAILike()

    p1 = BasePrompt(system_prompt="You are concise.", user_prompt="Summarize: {{query}}")
    p2 = BasePrompt(system_prompt="You are creative.", user_prompt="Give a metaphor for: {{query}}")
    p3 = BasePrompt(system_prompt="You are critical.", user_prompt="Give two risks: {{query}}")

    for p in (p1, p2, p3):
        p.add_llm(llm)

    # Two ways: explicit ParallelPrompt or `|` operator
    parallel_a = ParallelPrompt([p1, p2, p3])
    parallel_b = p1 | p2 | p3

    print("=== ParallelPrompt ===")
    results = await parallel_a.acall(query="an AI agent framework")
    for i, r in enumerate(results, 1):
        print(f"[A{i}] {r}")

    print("\n=== | Operator ===")
    results = await parallel_b.acall(query="an AI agent framework")
    for i, r in enumerate(results, 1):
        print(f"[B{i}] {r}")


if __name__ == "__main__":
    asyncio.run(main())
