"""
Tutorial 03: Async tools, parallel execution, hooks, and error handling.

This tutorial shows:
1) Define async tools with @tool.
2) Run multiple tool calls in parallel vs serial.
3) ToolRegistry hooks (before/after register).
4) ToolExecutor results + error_type.

Run:
  python tutorials/03_tool_parallel_and_async.py
"""

import asyncio
import json
import time

from alphora.tools import ToolRegistry, ToolExecutor, tool


@tool
async def slow_add(a: int, b: int, delay: float = 1.0) -> int:
    """Add two numbers after a delay."""
    await asyncio.sleep(delay)
    return a + b


@tool
async def slow_multiply(a: int, b: int, delay: float = 1.0) -> int:
    """Multiply two numbers after a delay."""
    await asyncio.sleep(delay)
    return a * b


def build_tool_calls() -> list[dict]:
    return [
        {
            "id": "call_1",
            "function": {
                "name": "slow_add",
                "arguments": json.dumps({"a": 10, "b": 7, "delay": 1.2}),
            },
        },
        {
            "id": "call_2",
            "function": {
                "name": "slow_multiply",
                "arguments": json.dumps({"a": 6, "b": 9, "delay": 1.4}),
            },
        },
        {
            "id": "call_3",
            "function": {
                "name": "slow_add",
                "arguments": json.dumps({"a": 3, "b": 5, "delay": 1.0}),
            },
        },
        {
            "id": "call_bad_args",
            "function": {
                "name": "slow_add",
                "arguments": json.dumps({"b": 1}),
            },
        },
        {
            "id": "call_not_found",
            "function": {
                "name": "not_registered_tool",
                "arguments": json.dumps({"x": 1}),
            },
        },
    ]


async def run_once(executor: ToolExecutor, parallel: bool) -> float:
    start = time.perf_counter()
    results = await executor.execute(build_tool_calls(), parallel=parallel)
    elapsed = time.perf_counter() - start

    mode = "parallel" if parallel else "serial"
    print(f"\n=== Results ({mode}) ===")
    for r in results:
        err = f", error_type={r.error_type}" if r.error_type else ""
        print(f"{r.tool_name} -> {r.content} ({r.status}{err})")

    return elapsed


async def main() -> None:
    def on_register(ctx):
        print(f"[register] {ctx.data.get('tool_name')}")

    registry = ToolRegistry(
        before_register=on_register,
        after_register=on_register,
    )
    registry.register(slow_add)
    registry.register(slow_multiply)

    executor = ToolExecutor(registry)

    t_serial = await run_once(executor, parallel=False)
    t_parallel = await run_once(executor, parallel=True)

    print("\n=== Timing ===")
    print(f"Serial:   {t_serial:.2f}s")
    print(f"Parallel: {t_parallel:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
