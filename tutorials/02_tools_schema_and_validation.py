"""
Tutorial 02: Tool schema, class methods, name_override, and validation.

This tutorial shows:
1) @tool generates OpenAI-compatible schema automatically.
2) Class instance methods can be registered as tools directly.
3) name_override resolves tool name conflicts.
4) Pydantic validation catches bad inputs early.
5) ToolExecutor executes tool calls.

Run:
  python tutorials/02_tools_schema_and_validation.py
"""

import asyncio
import json

from alphora.tools import ToolRegistry, ToolExecutor, tool
from alphora.tools.exceptions import ToolRegistrationError, ToolValidationError


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: 22°{unit[0].upper()}, Sunny"


class Calculator:
    def add(self, a: int, b: int) -> int:
        """Add two numbers (from class method)."""
        return a + b + 100


async def main() -> None:
    registry = ToolRegistry()
    registry.register(add)
    registry.register(get_weather)

    # Register a class method directly
    calc = Calculator()
    try:
        registry.register(calc.add)
    except ToolRegistrationError as exc:
        print("Name conflict:", exc)
        registry.register(calc.add, name_override="calc_add")

    print("=== OpenAI Tools Schema ===")
    schema = registry.get_openai_tools_schema()
    print(json.dumps(schema, ensure_ascii=False, indent=2))

    print("\n=== Valid Call ===")
    result = add.run(a=2, b=3)
    print(result)

    print("\n=== Invalid Call (missing required 'a') ===")
    try:
        add.run(b=1)  # type: ignore[arg-type]
    except ToolValidationError as exc:
        print("Validation error:", exc)

    print("\n=== ToolExecutor (parallel calls) ===")
    executor = ToolExecutor(registry)
    tool_calls = [
        {
            "id": "call_1",
            "function": {
                "name": "add",
                "arguments": json.dumps({"a": 10, "b": 7}),
            },
        },
        {
            "id": "call_2",
            "function": {
                "name": "calc_add",
                "arguments": json.dumps({"a": 1, "b": 2}),
            },
        },
    ]
    results = await executor.execute(tool_calls, parallel=True)
    for r in results:
        print(f"{r.tool_name} -> {r.content} ({r.status})")


if __name__ == "__main__":
    asyncio.run(main())
