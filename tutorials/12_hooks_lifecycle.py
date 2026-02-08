"""
Tutorial 12: Hook lifecycle + priority/when/timeout/fail_close/stop_propagation.

Run:
  python tutorials/12_hooks_lifecycle.py
"""

import asyncio
import os

from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.tools import tool
from alphora.hooks import HookManager, HookEvent, HookErrorPolicy
from alphora.hooks.result import HookResult


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def log_event(prefix: str):
    def _handler(ctx):
        print(f"[{prefix}] event={ctx.event}, component={ctx.component}")
        return None
    return _handler


async def main() -> None:
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("Missing env vars. Please set LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM.")
        return

    hooks = HookManager(default_timeout=1.0)
    hooks.register(HookEvent.AGENT_BEFORE_RUN, log_event("agent"))
    hooks.register(HookEvent.AGENT_AFTER_RUN, log_event("agent"))
    hooks.register(HookEvent.TOOLS_BEFORE_EXECUTE, log_event("tools"))
    hooks.register(HookEvent.TOOLS_AFTER_EXECUTE, log_event("tools"))

    # Priority and conditional execution
    def high_priority(ctx):
        print("[high_priority] before run")
        return None

    def only_first_iteration(ctx):
        return ctx.data.get("iteration") == 1

    hooks.register(
        HookEvent.AGENT_BEFORE_RUN,
        high_priority,
        priority=10,
    )
    hooks.register(
        HookEvent.AGENT_BEFORE_ITERATION,
        log_event("agent.iter"),
        when=only_first_iteration,
    )

    # fail_close example: raise to stop execution
    def strict_guard(ctx):
        if "forbidden" in (ctx.data.get("query") or ""):
            raise ValueError("forbidden keyword")

    hooks.register(
        HookEvent.AGENT_BEFORE_RUN,
        strict_guard,
        error_policy=HookErrorPolicy.FAIL_CLOSE,
    )

    # stop_propagation example
    def short_circuit(ctx):
        if ctx.data.get("query") == "ping":
            return HookResult(stop_propagation=True)

    hooks.register(HookEvent.AGENT_BEFORE_RUN, short_circuit, priority=20)

    agent = ReActAgent(
        llm=OpenAILike(),
        tools=[add],
        system_prompt="Use tools when needed.",
        hooks=hooks,
        max_iterations=3,
    )

    result = await agent.run("Compute 12 + 30 using the add tool.")
    print("\n=== Final Result ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
